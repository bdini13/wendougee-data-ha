"""Telemetry measurements only: no control entities."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfMass,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import WendougeeEntity

DESCRIPTIONS = (
    SensorEntityDescription(
        key="brew_boiler_temperature_celsius",
        name="Brew temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="steam_boiler_temperature_celsius",
        name="Steam temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure_bar",
        name="Pump pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dispensed_volume_ml",
        name="Pumped volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
    ),
    SensorEntityDescription(
        key="instantaneous_flow_ml_per_second",
        name="Flow rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.MILLILITERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="scale_weight_grams",
        name="Scale weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="weight_rate_grams_per_second",
        name="Weight rate",
        native_unit_of_measurement="g/s",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="elapsed_brew_time_seconds",
        name="Elapsed brew time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="pump_active_time_seconds",
        name="Pump active time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
    ),
)

ACTIVITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="observed_shots_total",
        name="Observed shots total",
        native_unit_of_measurement="shots",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key="observed_pumped_water_ml",
        name="Observed pumped water total",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key="last_shot_utc",
        name="Last observed shot",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:coffee",
    ),
    SensorEntityDescription(
        key="last_shot_volume_ml",
        name="Last observed shot volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        icon="mdi:cup-water",
    ),
    SensorEntityDescription(
        key="last_cleaning_utc",
        name="Last observed backflush",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:shimmer",
    ),
)

CONFIGURATION_DESCRIPTIONS = (
    SensorEntityDescription(
        key="steam_target_celsius",
        name="Steam target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="brew_target_celsius",
        name="Brew target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="manual_time_seconds",
        name="Manual time setting",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="manual_pressure_bar",
        name="Manual pressure setting",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cleaning_time_seconds",
        name="Cleaning time setting",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cleaning_rest_seconds",
        name="Cleaning rest setting",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="cleaning_repetitions",
        name="Cleaning repetitions setting",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="heating_mode",
        name="Heating mode setting",
        device_class=SensorDeviceClass.ENUM,
        options=["pulse", "full_speed"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

STATE_DESCRIPTIONS = (
    SensorEntityDescription(
        key="operating_state",
        name="Operating state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "idle",
            "profile",
            "manual",
            "cleaning",
            "free_variable",
            "ambiguous",
            "unknown",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Register measurements; provisional descriptions default to disabled."""
    async_add_entities(
        WendougeeSensor(entry, description)
        for description in (
            *DESCRIPTIONS,
            *ACTIVITY_DESCRIPTIONS,
            *CONFIGURATION_DESCRIPTIONS,
            *STATE_DESCRIPTIONS,
        )
    )


class WendougeeSensor(WendougeeEntity, SensorEntity):
    """Expose one decoded field; CoordinatorEntity owns freshness/availability."""

    def __init__(
        self, entry: ConfigEntry, description: SensorEntityDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        """Read the stored sample without triggering an extra device request."""
        if self.coordinator.data is None:
            return None
        key = self.entity_description.key
        if hasattr(self.coordinator.activity, key):
            return getattr(self.coordinator.activity, key)
        if hasattr(self.coordinator.data, key):
            return getattr(self.coordinator.data, key)
        if key == "operating_state":
            state = self.coordinator.operating_state
            return state.state if state is not None else None
        configuration = self.coordinator.configuration
        return getattr(configuration, key) if configuration is not None else None
