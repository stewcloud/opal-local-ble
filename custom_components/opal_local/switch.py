"""Documented Opal controls."""
from homeassistant.components.switch import SwitchEntity
from .entity import OpalEntity
from .protocol import enabled_state

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        OpalSwitch(entry.runtime_data, "enabled", "Ice making", "mdi:ice-pop"),
        OpalSwitch(entry.runtime_data, "night", "Night mode", "mdi:weather-night"),
    ])


class OpalSwitch(OpalEntity, SwitchEntity):
    @property
    def is_on(self):
        data = self.coordinator.data or {}
        if self.key == "enabled":
            return enabled_state(data)
        value = data.get("night")
        return bool(value) if value in (0, 1) else None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_command(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_command(self.key, False)
