"""Daily helper wiring, with every machine command replaced by a fake."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.wendougee_data._protocol.state import decode_configuration
from custom_components.wendougee_data.coordinator import WendougeeCoordinator
from tests.test_reads import register_response

from .test_integration import CONFIGURATION_VALUES, TELEMETRY, entry

pytestmark = pytest.mark.asyncio
MODULE = "custom_components.wendougee_data.schedules"
MORNING = datetime(2026, 9, 27, 6, 30, tzinfo=ZoneInfo("America/New_York"))


async def configured(hass):
    configured_entry = entry()
    configured_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        configured_entry, options={"allow_boiler_control": True}
    )
    await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"espresso_brew_schedule_enabled": {}}}
    )
    await hass.services.async_call(
        "input_boolean",
        "turn_on",
        {"entity_id": "input_boolean.espresso_brew_schedule_enabled"},
        blocking=True,
    )
    hass.states.async_set("input_datetime.espresso_brew_on_time", "06:30:00")
    hass.states.async_set("input_datetime.espresso_brew_off_time", "09:00:00")
    coordinator = WendougeeCoordinator(hass, configured_entry)
    coordinator.data = TELEMETRY
    return coordinator


async def test_setup_and_helper_edits_never_actuate(hass):
    coordinator = await configured(hass)
    with patch(f"{MODULE}.execute_boiler", new_callable=AsyncMock) as execute:
        await coordinator.schedules.async_setup()
        assert coordinator.schedules.diagnostics()["brew"]["listening"]
        hass.states.async_set("input_datetime.espresso_brew_on_time", "06:35:00")
        await hass.async_block_till_done()
        execute.assert_not_called()
        await coordinator.schedules.async_shutdown()
        assert not coordinator.schedules.diagnostics()["brew"]["listening"]


@pytest.mark.parametrize("enabled,hour,minute", [(True, 6, 30), (False, 9, 0)])
async def test_edge_verifies_feedback_and_persists_no_duplicate(
    hass, enabled, hour, minute
):
    coordinator = await configured(hass)
    words = list(CONFIGURATION_VALUES)
    words[7] = 0 if enabled else 1
    now = MORNING.replace(hour=hour, minute=minute)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=now),
        patch(
            f"{MODULE}.execute_boiler",
            return_value=decode_configuration(register_response(words)),
        ) as execute,
    ):
        await coordinator.schedules.async_run("brew", enabled)
        assert not coordinator.schedules.pending["brew"]
        restored = WendougeeCoordinator(hass, coordinator.entry)
        await restored.schedules.async_load()
        await restored.schedules.async_run("brew", enabled)
        assert execute.await_count == 1
    assert hass.states.is_state("input_boolean.espresso_brew_schedule_enabled", "on")
    assert coordinator.configuration.brew_heating_enabled is enabled


async def test_disabled_steam_and_outside_edge_do_not_actuate(hass):
    coordinator = await configured(hass)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING.replace(hour=12)),
        patch(f"{MODULE}.execute_boiler", new_callable=AsyncMock) as execute,
    ):
        await coordinator.schedules.async_run("steam", True)
        await coordinator.schedules.async_run("brew", True)
        execute.assert_not_called()


@pytest.mark.parametrize("failure", [TimeoutError, HomeAssistantError, OSError])
async def test_failure_pauses_helper_notifies_and_latches_across_reload(hass, failure):
    coordinator = await configured(hass)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch(
            f"{MODULE}.execute_boiler", side_effect=failure("private backend")
        ) as execute,
        patch(f"{MODULE}.persistent_notification.async_create") as notify,
    ):
        await coordinator.schedules.async_run("brew", True)
        assert coordinator.schedules.pending["brew"]
        assert hass.states.is_state(
            "input_boolean.espresso_brew_schedule_enabled", "off"
        )
        assert "private backend" not in str(notify.call_args)
        restored = WendougeeCoordinator(hass, coordinator.entry)
        await restored.schedules.async_load()
        assert restored.schedules.pending["brew"]
        await hass.services.async_call(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.espresso_brew_schedule_enabled"},
            blocking=True,
        )
        await restored.schedules.async_run("brew", True)
        assert execute.await_count == 1


async def test_cancelled_action_keeps_durable_uncertainty(hass):
    coordinator = await configured(hass)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch(f"{MODULE}.execute_boiler", side_effect=asyncio.CancelledError),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator.schedules.async_run("brew", True)
    restored = WendougeeCoordinator(hass, coordinator.entry)
    await restored.schedules.async_load()
    assert restored.schedules.pending["brew"]


async def test_store_failure_sends_no_command(hass):
    coordinator = await configured(hass)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch.object(coordinator.schedules.store, "async_save", side_effect=OSError),
        patch(f"{MODULE}.execute_boiler", new_callable=AsyncMock) as execute,
    ):
        await coordinator.schedules.async_run("brew", True)
        execute.assert_not_called()
    assert coordinator.schedules.pending["brew"]
    assert hass.states.is_state("input_boolean.espresso_brew_schedule_enabled", "off")


async def test_ack_requires_fresh_idle_and_does_not_enable_schedule(hass):
    coordinator = await configured(hass)
    await hass.services.async_call(
        "input_boolean",
        "turn_off",
        {"entity_id": "input_boolean.espresso_brew_schedule_enabled"},
        blocking=True,
    )
    coordinator.schedules.pending["brew"] = True
    with (
        patch(f"{MODULE}.verify_idle", side_effect=HomeAssistantError),
        pytest.raises(HomeAssistantError),
    ):
        await coordinator.schedules.async_acknowledge("brew")
    assert coordinator.schedules.pending["brew"]
    with patch(f"{MODULE}.verify_idle", new_callable=AsyncMock):
        await coordinator.schedules.async_acknowledge("brew")
    assert not coordinator.schedules.pending["brew"]
    assert hass.states.is_state("input_boolean.espresso_brew_schedule_enabled", "off")


async def test_real_local_time_listener_fires_only_future_edge(hass, freezer):
    from datetime import UTC, timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    dt_util.set_default_time_zone(ZoneInfo("America/New_York"))
    freezer.move_to(MORNING.astimezone(UTC) - timedelta(seconds=30))
    coordinator = await configured(hass)
    words = list(CONFIGURATION_VALUES)
    words[7] = 0
    with patch(
        f"{MODULE}.execute_boiler",
        return_value=decode_configuration(register_response(words)),
    ) as execute:
        await coordinator.schedules.async_setup()
        execute.assert_not_called()
        freezer.move_to(MORNING.astimezone(UTC) + timedelta(seconds=1))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        execute.assert_awaited_once()
        await coordinator.schedules.async_shutdown()


async def test_uncertain_state_after_wait_does_not_write(hass):
    coordinator = await configured(hass)

    async def acquire():
        coordinator.cleaning_start_locked = True

    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch.object(coordinator._connection_lock, "acquire", side_effect=acquire),
        patch.object(coordinator._connection_lock, "release"),
        patch(f"{MODULE}.execute_boiler", new_callable=AsyncMock) as execute,
    ):
        await coordinator.schedules.async_run("brew", True)
        execute.assert_not_called()


async def test_mismatched_readback_keeps_lock(hass):
    coordinator = await configured(hass)
    words = list(CONFIGURATION_VALUES)
    words[7] = 1
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch(
            f"{MODULE}.execute_boiler",
            return_value=decode_configuration(register_response(words)),
        ),
    ):
        await coordinator.schedules.async_run("brew", True)
    assert coordinator.schedules.pending["brew"]
    assert hass.states.is_state("input_boolean.espresso_brew_schedule_enabled", "off")


async def test_busy_timeout_does_not_queue_write(hass):
    coordinator = await configured(hass)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch.object(coordinator._connection_lock, "acquire", side_effect=TimeoutError),
        patch(f"{MODULE}.execute_boiler", new_callable=AsyncMock) as execute,
    ):
        await coordinator.schedules.async_run("brew", True)
        execute.assert_not_called()
    assert not coordinator.schedules.pending["brew"]
    assert hass.states.is_state("input_boolean.espresso_brew_schedule_enabled", "off")


async def test_multiple_machine_entries_cannot_share_schedule_helpers(hass):
    coordinator = await configured(hass)
    second = entry()
    second.add_to_hass(hass)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=MORNING),
        patch(f"{MODULE}.execute_boiler", new_callable=AsyncMock) as execute,
    ):
        await coordinator.schedules.async_run("brew", True)
        execute.assert_not_called()


async def test_fall_back_duplicate_on_is_skipped_even_after_off(hass):
    coordinator = await configured(hass)
    hass.states.async_set("input_datetime.espresso_brew_on_time", "01:30:00")
    hass.states.async_set("input_datetime.espresso_brew_off_time", "01:45:00")
    now = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"))

    async def verified(_hass, _address, _boiler, enabled):
        words = list(CONFIGURATION_VALUES)
        words[7] = 0 if enabled else 1
        return decode_configuration(register_response(words))

    with patch(f"{MODULE}.execute_boiler", side_effect=verified) as execute:
        for at, enabled in (
            (now, True),
            (now.replace(minute=45), False),
            (now.replace(fold=1), True),
        ):
            with patch(f"{MODULE}.dt_util.now", return_value=at):
                await coordinator.schedules.async_run("brew", enabled)
        assert execute.await_count == 2
