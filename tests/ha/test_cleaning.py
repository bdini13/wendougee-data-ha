"""Cleaning requires opt-in, single ownership and a durable uncertainty guard."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.wendougee_data._protocol.control_session import ControlRejected
from custom_components.wendougee_data.const import DOMAIN
from custom_components.wendougee_data.coordinator import WendougeeCoordinator
from tests.test_cleaning import CleaningMachine

from .test_integration import BASELINE_FRAMES, entry

pytestmark = pytest.mark.asyncio


def configured_coordinator(hass):
    configured = entry()
    configured.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        configured, options={"allow_cleaning_control": True}
    )
    return configured, WendougeeCoordinator(hass, configured)


async def test_cleaning_disabled_by_default(hass):
    with pytest.raises(HomeAssistantError, match="not enabled"):
        await WendougeeCoordinator(hass, entry()).async_start_cleaning()


async def test_cleaning_never_queues(hass):
    _, coordinator = configured_coordinator(hass)
    async with coordinator._connection_lock:
        with pytest.raises(HomeAssistantError, match="busy"):
            await coordinator.async_start_cleaning()


@pytest.mark.parametrize("failure", [TimeoutError, asyncio.CancelledError])
async def test_uncertain_cleaning_survives_reload_and_blocks_repeat(hass, failure):
    configured, coordinator = configured_coordinator(hass)
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.execute_cleaning",
            side_effect=failure,
        ),
        pytest.raises((HomeAssistantError, asyncio.CancelledError)),
    ):
        await coordinator.async_start_cleaning()
    restored = WendougeeCoordinator(hass, configured)
    await restored.async_load_control_state()
    assert restored.cleaning_start_locked
    with pytest.raises(HomeAssistantError, match="uncertain"):
        await restored.async_start_cleaning()


async def test_cleaning_precondition_rejection_unlocks_without_clearing_profile_guard(
    hass,
):
    configured, coordinator = configured_coordinator(hass)
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.execute_cleaning",
            side_effect=ControlRejected("idle required"),
        ),
        pytest.raises(HomeAssistantError, match="idle required"),
    ):
        await coordinator.async_start_cleaning()
    assert not coordinator.cleaning_start_locked
    await coordinator._save_profile_lock(True)
    restored = WendougeeCoordinator(hass, configured)
    await restored.async_load_control_state()
    assert restored.profile_start_locked
    assert not restored.cleaning_start_locked


async def test_profile_guard_save_does_not_erase_cleaning_guard(hass):
    configured, coordinator = configured_coordinator(hass)
    await coordinator._save_cleaning_lock(True)
    await coordinator._save_profile_lock(False)
    restored = WendougeeCoordinator(hass, configured)
    await restored.async_load_control_state()
    assert restored.cleaning_start_locked


async def test_failed_cleaning_guard_clear_stays_locked(hass):
    _, coordinator = configured_coordinator(hass)
    coordinator.cleaning_start_locked = True
    with (
        patch.object(coordinator._control_store, "async_save", side_effect=OSError),
        pytest.raises(OSError),
    ):
        await coordinator._save_cleaning_lock(False)
    assert coordinator.cleaning_start_locked


async def test_cleaning_button_setup_never_starts_machine(hass):
    configured, _ = configured_coordinator(hass)
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_baseline",
            return_value=BASELINE_FRAMES,
        ),
        patch(f"custom_components.{DOMAIN}.coordinator.execute_cleaning") as execute,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("button.wendougee_data_s_start_cleaning") is not None
        execute.assert_not_called()
        await hass.config_entries.async_unload(configured.entry_id)


async def test_runtime_observes_start_and_idle_and_never_changes_parameters(hass):
    from custom_components.wendougee_data.control import execute_cleaning

    class Finishes(CleaningMachine):
        async def send(self, request):
            await super().send(request)
            if request[1] == 1 and self.bits == 0x20:
                self.bits = 0

    machine = Finishes()
    observe = Mock()
    with (
        patch(
            f"custom_components.{DOMAIN}.control.HomeAssistantControlTransport",
            return_value=machine,
        ),
        patch(f"custom_components.{DOMAIN}.control.cleaning_duration", return_value=0),
        patch(
            f"custom_components.{DOMAIN}.control.asyncio.sleep", new_callable=AsyncMock
        ),
    ):
        result = await execute_cleaning(hass, "not-a-live-address", observe)
    assert result["settings_unchanged"]
    assert result["cleaning_count"] == 3
    assert result["observed_states"] == ["cleaning", "idle"]
    observed_states = [call.args[1].state for call in observe.call_args_list]
    assert observed_states[0] == "cleaning"
    assert observed_states[-2:] == ["idle", "idle"]
    assert machine.closed
    assert len([r for r in machine.sent if r[1] == 5]) == 2


async def test_successful_cleaning_clears_guard_and_returns_result(hass):
    configured, coordinator = configured_coordinator(hass)
    result = {"result": "cleaning_observed_then_idle", "settings_unchanged": True}
    with patch(
        f"custom_components.{DOMAIN}.coordinator.execute_cleaning", return_value=result
    ):
        assert await coordinator.async_start_cleaning() == result
    restored = WendougeeCoordinator(hass, configured)
    await restored.async_load_control_state()
    assert not restored.cleaning_start_locked


async def test_acknowledgement_requires_fresh_idle(hass):
    _, coordinator = configured_coordinator(hass)
    await coordinator._save_cleaning_lock(True)
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.verify_idle",
            side_effect=ControlRejected("busy"),
        ),
        pytest.raises(HomeAssistantError, match="remains locked"),
    ):
        await coordinator.async_acknowledge_cleaning_uncertainty()
    assert coordinator.cleaning_start_locked
    with patch(f"custom_components.{DOMAIN}.coordinator.verify_idle"):
        await coordinator.async_acknowledge_cleaning_uncertainty()
    assert not coordinator.cleaning_start_locked


@pytest.mark.parametrize("fault", ["alarm", "different_state"])
async def test_monitor_fault_does_not_send_another_pulse(hass, fault):
    from custom_components.wendougee_data.control import execute_cleaning

    class Fails(CleaningMachine):
        async def send(self, request):
            await super().send(request)
            if request[1] == 1 and self.bits == 0x20:
                if fault == "alarm":
                    self.alarm = True
                else:
                    self.bits = 1

    machine = Fails()
    with (
        patch(
            f"custom_components.{DOMAIN}.control.HomeAssistantControlTransport",
            return_value=machine,
        ),
        pytest.raises(ValueError, match="Unexpected"),
    ):
        await execute_cleaning(hass, "not-a-live-address", Mock())
    assert machine.closed
    assert len([r for r in machine.sent if r[1] == 5]) == 2
