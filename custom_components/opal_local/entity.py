"""Common entity identity and device registration."""
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class OpalEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.entry.title,
            manufacturer="GE / FirstBuild", model="Opal (first generation, BLE)",
        )
