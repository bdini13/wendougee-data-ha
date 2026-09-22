"""Shared device metadata without raw device identifiers."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_DISPLAY_NAME, DOMAIN, device_id
from .coordinator import WendougeeCoordinator


class WendougeeEntity(CoordinatorEntity[WendougeeCoordinator]):
    """Share HA availability and address-derived IDs across read-only entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data)
        identity = device_id(entry.data[CONF_ADDRESS])
        self._attr_unique_id = f"{identity}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            name=DEVICE_DISPLAY_NAME,
            manufacturer="Wendougee",
            model="DATA S",
        )
