"""Operating status and raw diagnostic values."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import OpalEntity
from .protocol import status_name

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        OpalSensor(entry.runtime_data, "status", "Status", "mdi:ice-pop"),
        OpalSensor(entry.runtime_data, "cleaning", "Cleaning phase", "mdi:spray-bottle"),
        OpalRawSensor(entry.runtime_data, "status", "Status code", "mdi:information-outline"),
    ])


class OpalSensor(OpalEntity, SensorEntity):
    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return status_name(data.get("status")) if self.key == "status" else data.get(self.key)


class OpalRawSensor(OpalSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator, key, name, icon)
        self._attr_unique_id += "_raw"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self.key)
