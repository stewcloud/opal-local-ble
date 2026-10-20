"""Opal bin position and water-needed sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .entity import OpalEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        OpalBinary(entry.runtime_data, "bin", "Bin removed", "mdi:tray-remove"),
        OpalBinary(entry.runtime_data, "needs_water", "Needs water", "mdi:water-alert"),
    ])


class OpalBinary(OpalEntity, BinarySensorEntity):
    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator, key, name, icon)
        self._attr_device_class = BinarySensorDeviceClass.OPENING if key == "bin" else BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        data = self.coordinator.data or {}
        value = data.get("bin" if self.key == "bin" else "status")
        if value is None:
            return None
        if self.key == "bin":
            return bool(value) if value in (0, 1) else None
        return value == 2 if value in range(5) else None
