"""Local BLE support for first-generation GE / FirstBuild Opal."""
from homeassistant.const import Platform

from .coordinator import OpalCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass, entry):
    coordinator = OpalCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
