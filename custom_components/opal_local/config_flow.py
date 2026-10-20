"""Discovery, manual address entry, validation, and polling options."""
from __future__ import annotations

import re
import logging
import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_INTERVAL, CONF_PAIR, CONF_SOURCE, DEFAULT_INTERVAL, DOMAIN
from .coordinator import OpalCoordinator

_LOGGER = logging.getLogger(__name__)


def source_choices(hass, current="auto"):
    choices = {"auto": "Automatic (HA selection with connection failover)"}
    for scanner in bluetooth.async_current_scanners(hass):
        if scanner.connectable:
            choices[scanner.source] = scanner.name
    if current not in choices:
        choices[current] = "Previously selected adapter/proxy (currently unavailable)"
    return choices


class OpalConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.address = None

    async def async_step_bluetooth(self, discovery_info):
        self.address = discovery_info.address.upper()
        await self.async_set_unique_id(self.address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": "Opal"}
        return await self.async_step_bluetooth_confirm()

    async def _validate(self, address, pair, source):
        # A temporary entry-like object allows exactly the same transaction as polling.
        from types import SimpleNamespace
        temporary = SimpleNamespace(data={CONF_ADDRESS: address}, options={CONF_PAIR: pair, CONF_SOURCE: source})
        coordinator = OpalCoordinator(self.hass, None)
        coordinator.address = address
        coordinator.entry = temporary
        await coordinator._async_update_data()

    async def _finish(self, address, pair, source):
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        await self._validate(address, pair, source)
        return self.async_create_entry(title="Opal", data={CONF_ADDRESS: address}, options={CONF_PAIR: pair, CONF_SOURCE: source})

    async def async_step_bluetooth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                return await self._finish(self.address, user_input[CONF_PAIR], user_input[CONF_SOURCE])
            except UpdateFailed as err:
                _LOGGER.warning("Opal setup failed: %s", err)
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="bluetooth_confirm", errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_PAIR, default=True): bool,
                vol.Required(CONF_SOURCE, default="auto"): vol.In(source_choices(self.hass)),
            }),
        )

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                try:
                    return await self._finish(address, user_input[CONF_PAIR], user_input[CONF_SOURCE])
                except UpdateFailed as err:
                    _LOGGER.warning("Opal setup failed: %s", err)
                    errors["base"] = "cannot_connect"
        discovered = [info.address for info in bluetooth.async_discovered_service_info(self.hass)
                      if (info.name or "").startswith("OPAL Bluetooth-")]
        return self.async_show_form(
            step_id="user", errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default=discovered[0] if discovered else ""): str,
                vol.Required(CONF_PAIR, default=True): bool,
                vol.Required(CONF_SOURCE, default="auto"): vol.In(source_choices(self.hass)),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OpalOptionsFlow()


class OpalOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_INTERVAL, default=self.config_entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            vol.Required(CONF_PAIR, default=self.config_entry.options.get(CONF_PAIR, True)): bool,
            vol.Required(CONF_SOURCE, default=self.config_entry.options.get(CONF_SOURCE, "auto")):
                vol.In(source_choices(self.hass, self.config_entry.options.get(CONF_SOURCE, "auto"))),
        }))
