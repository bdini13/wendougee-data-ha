"""Read-only configuration and operating-state entity coverage."""

import pytest

from custom_components.wendougee_data import binary_sensor, sensor
from custom_components.wendougee_data._protocol.state import (
    Configuration,
    OperatingState,
)
from custom_components.wendougee_data.coordinator import WendougeeCoordinator

from .test_integration import TELEMETRY, entry

pytestmark = pytest.mark.asyncio


async def test_configuration_and_operating_state_entities_are_read_only(hass):
    configured = entry()
    configured.add_to_hass(hass)
    coordinator = WendougeeCoordinator(hass, configured)
    coordinator.data = TELEMETRY
    coordinator.configuration = Configuration(
        cleaning_time_seconds=5.5,
        cleaning_rest_seconds=12.5,
        cleaning_repetitions=4,
        steam_heating_enabled=False,
        brew_heating_enabled=True,
        steam_target_celsius=125,
        brew_target_celsius=94,
        manual_time_seconds=31.5,
        manual_pressure_bar=8.5,
        heating_mode="full_speed",
        raw_registers=tuple([0] * 37),
    )
    coordinator.water_alarm_enabled = True
    coordinator.operating_state = OperatingState(
        raw_bits=16,
        profile_active=False,
        manual_active=True,
        cleaning_active=False,
        free_variable_active=False,
        unknown_bits=0,
    )
    configured.runtime_data = coordinator

    sensors = []
    binary_sensors = []
    await sensor.async_setup_entry(
        hass, configured, lambda entities: sensors.extend(list(entities))
    )
    await binary_sensor.async_setup_entry(
        hass, configured, lambda entities: binary_sensors.extend(list(entities))
    )

    assert len(sensors) == 18
    assert len(binary_sensors) == 5
    assert all(
        entity.entity_registry_enabled_default is False for entity in sensors[9:]
    )
    assert all(
        entity.entity_registry_enabled_default is False for entity in binary_sensors[2:]
    )
    assert not any(
        entity.platform.domain in {"switch", "button", "number", "select"}
        for entity in [*sensors, *binary_sensors]
        if entity.platform is not None
    )

    sensor_values = {
        entity.entity_description.key: entity.native_value for entity in sensors
    }
    expected_sensor_values = {
        "steam_target_celsius": 125,
        "brew_target_celsius": 94,
        "manual_time_seconds": 31.5,
        "manual_pressure_bar": 8.5,
        "cleaning_time_seconds": 5.5,
        "cleaning_rest_seconds": 12.5,
        "cleaning_repetitions": 4,
        "heating_mode": "full_speed",
        "operating_state": "manual",
    }
    assert {
        key: sensor_values[key] for key in expected_sensor_values
    } == expected_sensor_values

    binary_values = {
        entity.entity_description.key: entity.is_on for entity in binary_sensors
    }
    expected_binary_values = {
        "steam_heating_enabled": False,
        "brew_heating_enabled": True,
        "water_alarm_enabled": True,
    }
    assert {
        key: binary_values[key] for key in expected_binary_values
    } == expected_binary_values
