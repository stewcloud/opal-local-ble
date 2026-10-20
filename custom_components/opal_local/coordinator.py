"""Serialized, short-lived BLE transactions using HA's selected adapter."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import logging

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CHARACTERISTICS, CONF_INTERVAL, CONF_PAIR, CONF_SOURCE, DEFAULT_INTERVAL, DOMAIN, SERVICE
from .protocol import decode_byte

_LOGGER = logging.getLogger(__name__)


class OpalCoordinator(DataUpdateCoordinator):
    """Resolve an adapter each transaction and release its slot afterwards."""

    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL) if entry else DEFAULT_INTERVAL))
        self.address = entry.data["address"] if entry else ""
        self.entry = entry
        self.lock = asyncio.Lock()
        self.last_source = None

    def candidates(self):
        """Use HA's connectable devices, retaining each proxy's own backend."""
        selected = self.entry.options.get(CONF_SOURCE, "auto")
        devices = bluetooth.async_scanner_devices_by_address(self.hass, self.address, connectable=True)
        if selected != "auto":
            matches = [item for item in devices if item.scanner.source == selected]
            if not matches:
                raise BleakError("Selected Bluetooth adapter/proxy cannot currently reach Opal. Check active connections and range, or select Automatic.")
            return [(matches[0].ble_device, selected)]
        best = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if best is None:
            raise BleakError("Opal is not reachable through a connectable Bluetooth adapter/proxy")
        # Device objects carry the backend routing information; MAC strings do not.
        ordered = sorted(devices, key=lambda item: (item.ble_device is not best, -item.advertisement.rssi))
        candidates = [(item.ble_device, item.scanner.source) for item in ordered]
        if not candidates:
            candidates = [(best, None)]
        return candidates[:3]

    async def disconnect(self, client):
        try:
            async with asyncio.timeout(10):
                await client.disconnect()
        except (BleakError, TimeoutError, OSError):
            _LOGGER.debug("Could not cleanly disconnect Opal", exc_info=True)

    async def connect(self):
        """Fail over only before an operation starts; never replay writes."""
        last_error = None
        for device, source in self.candidates():
            client = None
            try:
                async with asyncio.timeout(25):
                    client = await establish_connection(
                        BleakClientWithServiceCache, device, "Opal", max_attempts=2,
                        pair=False,
                    )
                    # Explicit post-connect pairing is supported by ESPHome proxies
                    # advertising PAIRING. Do not rely on a backend honoring pair=
                    # during connection (older HA/Bleak combinations differ).
                    if self.entry.options.get(CONF_PAIR, True):
                        try:
                            await client.pair()
                        except NotImplementedError as err:
                            raise BleakError("This adapter/proxy does not support pairing. Update ESPHome proxy firmware (pairing requires 2024.3+), enable active connections, or use an adapter that supports bonding.") from err
                    if client.services.get_service(SERVICE) is None:
                        raise BleakError("The device does not expose the first-generation Opal service")
                self.last_source = source
                return client
            except BaseException as err:
                if client is not None:
                    await self.disconnect(client)
                if not isinstance(err, (BleakError, TimeoutError, OSError, NotImplementedError)):
                    raise
                last_error = err
                _LOGGER.debug("Opal connection candidate failed: %s", err)
        raise BleakError(f"Unable to connect/pair with Opal: {last_error}") from last_error

    @asynccontextmanager
    async def connection(self):
        async with self.lock:
            client = None
            try:
                async with asyncio.timeout(90):
                    client = await self.connect()
                    yield client
            finally:
                if client is not None:
                    await self.disconnect(client)

    async def read(self, client):
        data = {}
        for key, uuid in CHARACTERISTICS.items():
            char = client.services.get_characteristic(uuid)
            if char is None or "read" not in char.properties:
                if key == "status":
                    raise BleakError("Required status characteristic is not readable")
                continue
            data[key] = decode_byte(await client.read_gatt_char(char))
        return data

    async def _async_update_data(self):
        try:
            async with self.connection() as client:
                try:
                    return await self.read(client)
                except BleakError as err:
                    if not self.entry.options.get(CONF_PAIR, True) or not is_authentication_error(err):
                        raise
                    # A bond is persistent, but encryption/authentication is per
                    # connection. Retry reads only, never an appliance command.
                    await client.pair()
                    return await self.read(client)
        except (BleakError, TimeoutError, OSError, ValueError, NotImplementedError) as err:
            if is_authentication_error(err):
                raise UpdateFailed("Opal rejected Bluetooth authentication. Enable pairing and select the intended proxy. If this persists, repair that proxy's Opal bond; pairing on a different adapter is not shared.") from err
            raise UpdateFailed(f"Opal Bluetooth update failed: {err}") from err

    async def async_command(self, key: str, enabled: bool):
        """Only write documented, idempotent boolean commands."""
        if key not in ("enabled", "night"):
            raise HomeAssistantError("Unsupported Opal command")
        try:
            async with self.connection() as client:
                char = client.services.get_characteristic(CHARACTERISTICS[key])
                if char is None:
                    raise BleakError("Control characteristic is missing")
                if "write" in char.properties:
                    response = True
                elif "write-without-response" in char.properties:
                    response = False
                else:
                    raise BleakError("Control characteristic is not writable")
                await client.write_gatt_char(char, bytes([int(enabled)]), response=response)
            # Poll separately so failed status verification never replays a command.
            await self.async_request_refresh()
        except (BleakError, TimeoutError, OSError, ValueError, NotImplementedError) as err:
            raise HomeAssistantError(f"Opal command failed: {err}") from err


def is_authentication_error(err):
    """Recognize security failures without treating every GATT error as auth."""
    message = str(err).lower()
    return any(word in message for word in (
        "authentication", "insufficient encryption", "insufficient authorization",
    ))
