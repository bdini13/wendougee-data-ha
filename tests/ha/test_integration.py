"""Real HA config-flow and entity lifecycle tests with synthetic telemetry."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wendougee_data import async_setup
from custom_components.wendougee_data._protocol.crc import append_crc
from custom_components.wendougee_data._protocol.reads import ReadOperation
from custom_components.wendougee_data._protocol.state import decode_operating_state
from custom_components.wendougee_data._protocol.telemetry import (
    parse_telemetry_response,
)
from custom_components.wendougee_data.const import (
    CONF_CAPTURE_BASELINE,
    DOMAIN,
    PRIVATE_BASELINE_FILE,
    SERVICE_CAPTURE_BASELINE,
    device_id,
)
from custom_components.wendougee_data.diagnostics import (
    async_get_config_entry_diagnostics,
)
from tests.test_reads import register_response
from tests.test_telemetry import TELEMETRY_RESPONSE

pytestmark = pytest.mark.asyncio
ADDRESS = "00:00:00:00:00:01"  # Synthetic, not a real device identifier.
TELEMETRY = parse_telemetry_response(TELEMETRY_RESPONSE)
CONFIGURATION_VALUES = [0] * 37
for register, value in {
    0: 55,
    1: 125,
    2: 4,
    6: 1,
    7: 0,
    8: 125,
    9: 94,
    17: 315,
    19: 85,
    22: 1,
}.items():
    CONFIGURATION_VALUES[register] = value
IDLE_STATE_FRAME = append_crc(b"\x01\x01\x03" + bytes(3))
IDLE_STATE = decode_operating_state(IDLE_STATE_FRAME)
BASELINE_FRAMES = {
    ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
    ReadOperation.CONFIGURATION: register_response(CONFIGURATION_VALUES),
    ReadOperation.WATER_ALARM_ENABLED: register_response([1]),
    ReadOperation.OPERATING_STATE: IDLE_STATE_FRAME,
}


def entry(*, capture_baseline=False):
    data = {CONF_ADDRESS: ADDRESS, "poll_interval": 30}
    if capture_baseline:
        data[CONF_CAPTURE_BASELINE] = True
    return MockConfigEntry(
        domain=DOMAIN,
        title="Wendougee DATA",
        unique_id=device_id(ADDRESS),
        data=data,
    )


def discovery(address=ADDRESS, name="WDG_Data_test", connectable=True):
    from types import SimpleNamespace

    return SimpleNamespace(address=address, name=name, connectable=connectable)


async def test_bluetooth_requires_confirmation_and_never_connects_in_flow(hass):
    with (
        patch(f"custom_components.{DOMAIN}.async_setup_entry", return_value=True),
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_baseline",
            new_callable=AsyncMock,
        ) as read,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=discovery()
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"confirm": False, "poll_interval": 30}
        )
        assert result["errors"] == {"base": "confirmation_required"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"confirm": True, "poll_interval": 30}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == device_id(ADDRESS)
        assert ADDRESS not in result["result"].unique_id
        read.assert_not_called()


async def test_bluetooth_discovery_uses_explicit_yaml_polling_opt_in(hass):
    hass.data[DOMAIN] = {"yaml_import": True}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=discovery()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        CONF_ADDRESS: ADDRESS,
        "poll_interval": 30,
    }


async def test_duplicate_discovery_and_case_normalization(hass):
    configured = entry()
    configured.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=discovery()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert device_id("aa:bb:cc:dd:ee:ff") == device_id("AA:BB:CC:DD:EE:FF")


@pytest.mark.parametrize(
    "info", [discovery(name="Other"), discovery(connectable=False)]
)
async def test_unsupported_discovery(hass, info):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=info
    )
    assert result["reason"] == "not_supported"


async def test_user_selection_uses_shared_discoveries(hass):
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[discovery(), discovery(name="Other")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        assert result["step_id"] == "confirm"


async def test_no_discovered_devices(hass):
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["reason"] == "no_devices_found"


async def test_yaml_setup_waits_for_shared_bluetooth_discovery(hass):
    with (
        patch(
            "custom_components.wendougee_data.ha_bluetooth.async_discovered_service_info",
            side_effect=[[], [discovery()]],
        ) as discoveries,
        patch(
            "custom_components.wendougee_data.asyncio.sleep", new_callable=AsyncMock
        ) as sleep,
        patch.object(
            hass.config_entries.flow, "async_init", new_callable=AsyncMock
        ) as start_flow,
    ):
        assert await async_setup(hass, {DOMAIN: {}})
        await hass.async_block_till_done(wait_background_tasks=True)
    assert discoveries.call_count == 2
    sleep.assert_any_await(2)
    assert sum(call.args == (2,) for call in sleep.await_args_list) == 1
    start_flow.assert_awaited_once_with(DOMAIN, context={"source": SOURCE_IMPORT})


async def test_yaml_import_uses_exactly_one_shared_discovery(hass):
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[discovery(), discovery(name="Other")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        CONF_ADDRESS: ADDRESS,
        "poll_interval": 30,
    }


async def test_yaml_import_refuses_ambiguous_machine_selection(hass):
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[discovery(), discovery(address="00:00:00:00:00:02")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "multiple_devices_found"


async def test_setup_entities_failure_recovery_diagnostics_and_unload(hass):
    configured = entry()
    configured.add_to_hass(hass)
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_baseline",
            new_callable=AsyncMock,
            return_value=BASELINE_FRAMES,
        ),
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_runtime",
            new_callable=AsyncMock,
            return_value=(TELEMETRY, IDLE_STATE),
        ) as read,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        coordinator = configured.runtime_data
        states = hass.states.async_all()
        brew = next(
            state
            for state in states
            if state.attributes.get("friendly_name", "").endswith("Brew temperature")
        )
        assert float(brew.state) == 93.6
        assert brew.attributes["unit_of_measurement"] == "°C"
        assert not any(
            state.domain in {"switch", "button", "number", "select"} for state in states
        )
        read.side_effect = ConnectionError(f"private {ADDRESS}")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(brew.entity_id).state == "unavailable"
        reachable = next(
            state
            for state in hass.states.async_all()
            if state.attributes.get("friendly_name", "").endswith("Reachable")
        )
        assert reachable.state == "off"
        diagnostics = await async_get_config_entry_diagnostics(hass, configured)
        assert diagnostics["schema_version"] == 2
        assert diagnostics["configuration"]["brew_target_celsius"] == 94
        assert "raw_registers" not in diagnostics["configuration"]
        assert diagnostics["water_alarm_enabled"] is True
        assert diagnostics["operating_state"] == {
            "state": "idle",
            "profile_active": False,
            "manual_active": False,
            "cleaning_active": False,
            "free_variable_active": False,
            "unknown_bits": 0,
        }
        assert ADDRESS not in str(diagnostics)
        assert device_id(ADDRESS) not in str(diagnostics)
        assert "private" not in str(diagnostics)
        read.side_effect = None
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert float(hass.states.get(brew.entity_id).state) == 93.6
        assert await hass.config_entries.async_unload(configured.entry_id)
        await hass.async_block_till_done()
        assert coordinator.stopped


async def test_first_read_failure_uses_ha_setup_retry(hass):
    configured = entry()
    configured.add_to_hass(hass)
    with patch(
        f"custom_components.{DOMAIN}.coordinator.read_baseline",
        new_callable=AsyncMock,
        side_effect=TimeoutError,
    ):
        assert not await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
    assert configured.state.name == "SETUP_RETRY"


async def test_private_baseline_service_returns_only_four_allowlisted_frames(hass):
    from custom_components.wendougee_data._protocol.reads import (
        build_read_request,
    )

    configured = entry()
    configured.add_to_hass(hass)
    frames = {
        ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
        ReadOperation.CONFIGURATION: append_crc(b"\x01\x03\x4a" + bytes(74)),
        ReadOperation.WATER_ALARM_ENABLED: append_crc(b"\x01\x03\x02\x00\x01"),
        ReadOperation.OPERATING_STATE: append_crc(b"\x01\x01\x03\x00\x00\x00"),
    }
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_baseline",
            new_callable=AsyncMock,
            return_value=frames,
        ) as baseline,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_CAPTURE_BASELINE,
            {
                "config_entry_id": configured.entry_id,
                "confirmation": "READ ONLY",
            },
            blocking=True,
            return_response=True,
        )

    assert baseline.await_count == 2
    baseline.assert_awaited_with(hass, ADDRESS)
    assert response == {
        "schema": "wendougee-data-private-baseline/v1",
        "privacy_status": "private_unreviewed",
        "records": [
            {
                "operation": operation.name.lower(),
                "request_hex": build_read_request(operation).hex(),
                "response_hex": frames[operation].hex(),
            }
            for operation in ReadOperation
        ],
    }
    assert ADDRESS not in str(response)


async def test_headless_capture_writes_private_frames_only_once(hass, tmp_path):
    import json

    hass.config.config_dir = str(tmp_path)
    configured = entry(capture_baseline=True)
    configured.add_to_hass(hass)
    frames = {
        ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
        ReadOperation.CONFIGURATION: append_crc(b"\x01\x03\x4a" + bytes(74)),
        ReadOperation.WATER_ALARM_ENABLED: append_crc(b"\x01\x03\x02\x00\x01"),
        ReadOperation.OPERATING_STATE: append_crc(b"\x01\x01\x03\x00\x00\x00"),
    }
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_baseline",
            new_callable=AsyncMock,
            return_value=frames,
        ) as baseline,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(configured.entry_id)
        await hass.async_block_till_done()

    assert baseline.await_count == 2
    from pathlib import Path

    destination = Path(hass.config.path(PRIVATE_BASELINE_FILE))
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert destination.stat().st_mode & 0o777 == 0o600
    assert document["privacy_status"] == "private_unreviewed"
    assert [record["operation"] for record in document["records"]] == [
        operation.name.lower() for operation in ReadOperation
    ]
    assert ADDRESS not in str(document)


async def test_all_measurements_units_disabled_defaults_and_stable_ids(
    hass, entity_registry
):
    from homeassistant.helpers import entity_registry as er

    configured = entry()
    configured.add_to_hass(hass)
    with patch(
        f"custom_components.{DOMAIN}.coordinator.read_baseline",
        new_callable=AsyncMock,
        return_value=BASELINE_FRAMES,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(
            entity_registry, configured.entry_id
        )
        assert len(entities) == 23
        assert sum(item.disabled_by is not None for item in entities) == 17
        identities = {item.unique_id: item.entity_id for item in entities}
        assert all(ADDRESS not in identity for identity in identities)
        for item in entities:
            if item.disabled_by:
                entity_registry.async_update_entity(item.entity_id, disabled_by=None)
        assert await hass.config_entries.async_reload(configured.entry_id)
        await hass.async_block_till_done()
        expectations = {
            "brew_boiler_temperature_celsius": (93.6, "°C"),
            "steam_boiler_temperature_celsius": (125.4, "°C"),
            "pressure_bar": (8.7, "bar"),
            "dispensed_volume_ml": (42, "mL"),
            "instantaneous_flow_ml_per_second": (6, "mL/s"),
            "scale_weight_grams": (18.7, "g"),
            "weight_rate_grams_per_second": (2.3, "g/s"),
            "elapsed_brew_time_seconds": (12.3, "s"),
            "pump_active_time_seconds": (9, "s"),
            "steam_target_celsius": (125, "°C"),
            "brew_target_celsius": (94, "°C"),
            "manual_time_seconds": (31.5, "s"),
            "manual_pressure_bar": (8.5, "bar"),
            "cleaning_time_seconds": (5.5, "s"),
            "cleaning_rest_seconds": (12.5, "s"),
            "cleaning_repetitions": (4, None),
        }
        for key, (value, unit) in expectations.items():
            identity = f"{device_id(ADDRESS)}_{key}"
            state = hass.states.get(identities[identity])
            assert float(state.state) == value
            assert state.attributes.get("unit_of_measurement") == unit
        assert (
            hass.states.get(identities[f"{device_id(ADDRESS)}_water_level_alarm"]).state
            == "on"
        )
        for key, expected in {
            "steam_heating_enabled": "off",
            "brew_heating_enabled": "on",
            "water_alarm_enabled": "on",
            "heating_mode": "full_speed",
            "operating_state": "idle",
        }.items():
            entity_state = hass.states.get(identities[f"{device_id(ADDRESS)}_{key}"])
            assert entity_state.state == expected
        after = er.async_entries_for_config_entry(entity_registry, configured.entry_id)
        assert {item.unique_id: item.entity_id for item in after} == identities
        await hass.config_entries.async_unload(configured.entry_id)
