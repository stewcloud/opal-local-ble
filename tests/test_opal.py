"""Offline protocol and coordinator tests. Not an HA runtime emulator."""
import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "opal_local"

# Load relative protocol modules without running the HA integration __init__.
package = types.ModuleType("opal_under_test")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package


def module(name):
    return importlib.import_module("opal_under_test." + name)


class ProtocolTests(unittest.TestCase):
    def test_exactly_one_byte(self):
        decoder = module("protocol").decode_byte
        self.assertEqual(decoder(b"\x04"), 4)
        for value in (b"", b"\x01\x02"):
            with self.assertRaises(ValueError):
                decoder(value)

    def test_unknown_status_is_not_off(self):
        self.assertEqual(module("protocol").status_name(255), "unknown")

    def test_idle_or_no_water_does_not_mean_disabled(self):
        enabled = module("protocol").enabled_state
        for state in (2, 3, 4, 255):
            self.assertIsNone(enabled({"status": state}))
        self.assertTrue(enabled({"status": 3, "enabled": 1}))
        self.assertFalse(enabled({"status": 1, "enabled": 0}))
        self.assertTrue(enabled({"status": 1}))
        self.assertFalse(enabled({"status": 0}))


class FakeBleakError(Exception):
    pass


class FakeHAError(Exception):
    pass


class FakeUpdateFailed(Exception):
    pass


class FakeCoordinator:
    def __init__(self, hass, logger, **kwargs):
        self.hass = hass
        self.update_interval = kwargs.get("update_interval")
        self.async_request_refresh = AsyncMock()


def stub_modules():
    values = {}
    for name in ("bleak", "bleak_retry_connector", "homeassistant", "homeassistant.components",
                 "homeassistant.components.bluetooth", "homeassistant.exceptions",
                 "homeassistant.helpers", "homeassistant.helpers.update_coordinator"):
        values[name] = types.ModuleType(name)
    values["bleak"].BleakError = FakeBleakError
    values["bleak"].BleakClient = object
    values["bleak_retry_connector"].establish_connection = AsyncMock()
    values["bleak_retry_connector"].BleakClientWithServiceCache = object
    values["homeassistant.components.bluetooth"].async_ble_device_from_address = lambda *a, **kw: object()
    values["homeassistant.components.bluetooth"].async_scanner_devices_by_address = lambda *a, **kw: []
    values["homeassistant.exceptions"].HomeAssistantError = FakeHAError
    values["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = FakeCoordinator
    values["homeassistant.helpers.update_coordinator"].UpdateFailed = FakeUpdateFailed
    return values


class FakeServices:
    def __init__(self, chars):
        self.chars = chars

    def get_service(self, uuid):
        return object()

    def get_characteristic(self, uuid):
        return self.chars.get(uuid)


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.modules = patch.dict(sys.modules, stub_modules())
        self.modules.start()
        sys.modules.pop("opal_under_test.coordinator", None)
        self.m = module("coordinator")
        entry = types.SimpleNamespace(data={"address": "AA:BB:CC:DD:EE:FF"}, options={})
        self.coordinator = self.m.OpalCoordinator(object(), entry)
        self.uuids = module("const").CHARACTERISTICS
        self.chars = {uuid: types.SimpleNamespace(uuid=uuid, properties=["read", "write"])
                      for uuid in self.uuids.values()}
        self.client = types.SimpleNamespace(
            services=FakeServices(self.chars), disconnect=AsyncMock(), pair=AsyncMock(),
            read_gatt_char=AsyncMock(return_value=bytearray([1])), write_gatt_char=AsyncMock())
        self.m.establish_connection.return_value = self.client

    async def asyncTearDown(self):
        self.modules.stop()

    async def test_poll_and_release(self):
        data = await self.coordinator._async_update_data()
        self.assertEqual(data["status"], 1)
        self.client.disconnect.assert_awaited_once()

    async def test_read_failure_releases_connection(self):
        self.client.read_gatt_char.side_effect = FakeBleakError("bad read")
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()
        self.client.disconnect.assert_awaited_once()

    async def test_malformed_reply_fails_poll(self):
        self.client.read_gatt_char.return_value = b""
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()
        self.client.disconnect.assert_awaited_once()

    async def test_missing_optional_read_is_unknown(self):
        del self.chars[self.uuids["enabled"]]
        data = await self.coordinator._async_update_data()
        self.assertNotIn("enabled", data)

    async def test_missing_required_status_fails(self):
        del self.chars[self.uuids["status"]]
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()

    async def test_command_uses_acknowledged_write_then_refreshes(self):
        await self.coordinator.async_command("enabled", False)
        self.client.write_gatt_char.assert_awaited_once_with(
            self.chars[self.uuids["enabled"]], b"\x00", response=True)
        self.coordinator.async_request_refresh.assert_awaited_once()
        self.client.disconnect.assert_awaited_once()

    async def test_write_without_response_only_backend(self):
        char = self.chars[self.uuids["night"]]
        char.properties = ["write-without-response"]
        await self.coordinator.async_command("night", True)
        self.client.write_gatt_char.assert_awaited_once_with(char, b"\x01", response=False)

    async def test_failed_write_is_not_replayed(self):
        self.client.write_gatt_char.side_effect = FakeBleakError("failed")
        with self.assertRaises(FakeHAError):
            await self.coordinator.async_command("night", True)
        self.assertEqual(self.client.write_gatt_char.await_count, 1)
        self.coordinator.async_request_refresh.assert_not_awaited()
        self.client.disconnect.assert_awaited_once()

    async def test_no_reachable_adapter(self):
        self.m.bluetooth.async_ble_device_from_address = lambda *a, **kw: None
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()
        self.m.establish_connection.assert_not_awaited()

    async def test_invalid_command_never_connects(self):
        with self.assertRaises(FakeHAError):
            await self.coordinator.async_command("cleaning", True)
        self.m.establish_connection.assert_not_awaited()

    async def test_transactions_are_serialized(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        async def first():
            async with self.coordinator.connection():
                entered.set()
                await release.wait()
        task = asyncio.create_task(first())
        await entered.wait()
        second = asyncio.create_task(self.coordinator._async_update_data())
        await asyncio.sleep(0)
        self.assertEqual(self.m.establish_connection.await_count, 1)
        release.set()
        await task
        await second
        self.assertEqual(self.m.establish_connection.await_count, 2)

    async def test_pairing_backend_unsupported_is_reported(self):
        self.m.establish_connection.side_effect = NotImplementedError("Pairing unsupported")
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()

    async def test_flow_probe_can_create_coordinator_without_entry(self):
        self.assertEqual(self.m.OpalCoordinator(object(), None).address, "")

    def scanner_device(self, source, rssi=-60):
        return types.SimpleNamespace(ble_device=object(), scanner=types.SimpleNamespace(source=source),
                                     advertisement=types.SimpleNamespace(rssi=rssi))

    async def test_authenticate_every_new_connection(self):
        await self.coordinator._async_update_data()
        await self.coordinator._async_update_data()
        self.assertEqual(self.client.pair.await_count, 2)
        self.assertFalse(self.m.establish_connection.call_args.kwargs["pair"])

    async def test_pairing_can_be_disabled(self):
        self.coordinator.entry.options["pair"] = False
        await self.coordinator._async_update_data()
        self.client.pair.assert_not_awaited()

    async def test_selected_proxy_uses_its_backend_device(self):
        node = self.scanner_device("selected-proxy")
        self.m.bluetooth.async_scanner_devices_by_address = lambda *a, **kw: [node]
        self.coordinator.entry.options["bluetooth_source"] = "selected-proxy"
        await self.coordinator._async_update_data()
        self.assertIs(self.m.establish_connection.call_args.args[1], node.ble_device)

    async def test_selected_proxy_missing_does_not_silently_switch(self):
        self.coordinator.entry.options["bluetooth_source"] = "missing"
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()
        self.m.establish_connection.assert_not_awaited()

    async def test_auto_fails_over_before_writing(self):
        nodes = [self.scanner_device("proxy-a", -50), self.scanner_device("proxy-b", -60)]
        self.m.bluetooth.async_scanner_devices_by_address = lambda *a, **kw: nodes
        self.m.establish_connection.side_effect = [FakeBleakError("no slot"), self.client]
        await self.coordinator.async_command("night", True)
        self.assertIs(self.m.establish_connection.call_args.args[1], nodes[1].ble_device)
        self.assertEqual(self.client.write_gatt_char.await_count, 1)

    async def test_failed_pairing_releases_client(self):
        self.client.pair.side_effect = NotImplementedError("old firmware")
        with self.assertRaisesRegex(FakeUpdateFailed, "Update ESPHome"):
            await self.coordinator._async_update_data()
        self.client.disconnect.assert_awaited_once()

    async def test_poll_default_is_ten_seconds(self):
        self.assertEqual(self.coordinator.update_interval.total_seconds(), 10)

    async def test_auth_read_reauthenticates_and_retries_once(self):
        self.client.read_gatt_char.side_effect = [FakeBleakError("Insufficient authentication")] + [b"\x01"] * 5
        data = await self.coordinator._async_update_data()
        self.assertEqual(data["status"], 1)
        self.assertEqual(self.client.pair.await_count, 2)
        self.client.write_gatt_char.assert_not_awaited()

    async def test_persistent_auth_failure_is_bounded_and_actionable(self):
        self.client.read_gatt_char.side_effect = FakeBleakError("Insufficient authentication")
        with self.assertRaisesRegex(FakeUpdateFailed, "repair that proxy"):
            await self.coordinator._async_update_data()
        self.assertEqual(self.client.read_gatt_char.await_count, 2)
        self.assertEqual(self.client.pair.await_count, 2)
        self.client.disconnect.assert_awaited_once()

    async def test_pairing_disabled_does_not_retry_auth_reads(self):
        self.coordinator.entry.options["pair"] = False
        self.client.read_gatt_char.side_effect = FakeBleakError("Insufficient authentication")
        with self.assertRaises(FakeUpdateFailed):
            await self.coordinator._async_update_data()
        self.client.pair.assert_not_awaited()
        self.assertEqual(self.client.read_gatt_char.await_count, 1)


class FakeFlow:
    def __init_subclass__(cls, **kwargs):
        pass

    def _async_current_ids(self):
        return getattr(self, "configured", set())

    def async_show_form(self, **kwargs):
        return kwargs


class FlowTests(unittest.IsolatedAsyncioTestCase):
    """Exercise real flow discovery/selection using minimal API boundaries."""
    async def asyncSetUp(self):
        stubs = stub_modules()
        for name in ("homeassistant.config_entries", "homeassistant.const", "homeassistant.core", "voluptuous"):
            stubs[name] = types.ModuleType(name)
        stubs["homeassistant.config_entries"].ConfigFlow = FakeFlow
        stubs["homeassistant.config_entries"].OptionsFlow = FakeFlow
        stubs["homeassistant.const"].CONF_ADDRESS = "address"
        stubs["homeassistant.core"].callback = lambda function: function
        vol = stubs["voluptuous"]
        vol.Required = lambda key, **kwargs: key
        vol.In = lambda choices: choices
        vol.Schema = lambda schema: schema
        self.bt = stubs["homeassistant.components.bluetooth"]
        self.bt.async_request_active_scan = AsyncMock()
        self.devices = []
        self.bt.async_discovered_service_info = lambda *a, **kwargs: self.devices
        self.modules = patch.dict(sys.modules, stubs)
        self.modules.start()
        for name in ("coordinator", "config_flow"):
            sys.modules.pop("opal_under_test." + name, None)
        self.m = module("config_flow")
        self.flow = self.m.OpalConfigFlow()
        self.flow.hass = object()

    async def asyncTearDown(self):
        self.modules.stop()

    def device(self, name, address="AA:BB:CC:DD:EE:FF", services=()):
        return types.SimpleNamespace(name=name, address=address, service_uuids=services, rssi=-62)

    async def test_initial_scan_lists_matching_devices(self):
        self.devices.extend([self.device("OPAL Bluetooth-123"), self.device("Unrelated", "00:11:22:33:44:55")])
        result = await self.flow.async_step_user()
        choices = result["data_schema"]["device"]
        self.assertIn("AA:BB:CC:DD:EE:FF", choices)
        self.assertNotIn("00:11:22:33:44:55", choices)
        self.assertIn("-62 dBm", choices["AA:BB:CC:DD:EE:FF"])
        self.bt.async_request_active_scan.assert_awaited_once()

    async def test_service_uuid_match_without_name(self):
        self.devices.append(self.device(None, services=[module("const").SERVICE]))
        self.assertIn("AA:BB:CC:DD:EE:FF", self.flow._device_choices())

    async def test_configured_device_is_excluded(self):
        self.devices.append(self.device("OPAL Bluetooth-123"))
        self.flow.configured = {"aa:bb:cc:dd:ee:ff"}
        self.assertFalse(self.flow._device_choices())

    async def test_empty_scan_still_allows_rescan_or_manual(self):
        result = await self.flow.async_step_user()
        self.assertEqual(set(result["data_schema"]["device"]), {"scan_again", "manual"})

    async def test_rescan_requests_fresh_ha_sweep(self):
        await self.flow.async_step_user({"device": "scan_again"})
        self.bt.async_request_active_scan.assert_awaited_once_with(self.flow.hass, duration=5)

    async def test_device_selection_opens_connection_options(self):
        self.devices.append(self.device("OPAL Bluetooth-123"))
        self.flow.async_step_bluetooth_confirm = AsyncMock(return_value={"step_id": "bluetooth_confirm"})
        result = await self.flow.async_step_user({"device": "AA:BB:CC:DD:EE:FF"})
        self.assertEqual(self.flow.address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(result["step_id"], "bluetooth_confirm")

    async def test_manual_path_remains_available(self):
        result = await self.flow.async_step_user({"device": "manual"})
        self.assertEqual(result["step_id"], "manual")

    async def test_disappeared_selection_is_rejected(self):
        result = await self.flow.async_step_user({"device": "AA:BB:CC:DD:EE:FF"})
        self.assertEqual(result["errors"]["base"], "device_not_found")

    async def test_manual_address_validation(self):
        result = await self.flow.async_step_manual({"address": "invalid"})
        self.assertEqual(result["errors"]["address"], "invalid_address")


if __name__ == "__main__":
    unittest.main()
