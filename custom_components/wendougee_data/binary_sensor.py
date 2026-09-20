"""Water alarm and last-poll reachability; neither is a safety interlock."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import WendougeeEntity

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="water_level_alarm",
        name="Water shortage",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="reachable",
        name="Reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Register the reported alarm and separate last-poll reachability signal."""
    async_add_entities(WendougeeBinarySensor(entry, desc) for desc in DESCRIPTIONS)


class WendougeeBinarySensor(WendougeeEntity, BinarySensorEntity):
    """Read-only state; neither entity may be used as a physical safety interlock."""

    def __init__(self, entry: ConfigEntry, description: BinarySensorEntityDescription):
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Keep reachability visible as off when measurement entities go unavailable."""
        if self.entity_description.key == "reachable":
            return True
        return super().available

    @property
    def is_on(self) -> bool | None:
        """Reachability is last-poll success, not a continuously held BLE connection."""
        if self.entity_description.key == "reachable":
            return self.coordinator.last_update_success and not self.coordinator.stopped
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.water_level_alarm
