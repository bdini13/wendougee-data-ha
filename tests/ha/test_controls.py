"""Opt-in controls never run during setup; commands and failures stay bounded."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.wendougee_data._protocol.controls import BoilerSetting
from custom_components.wendougee_data._protocol.state import decode_configuration
from custom_components.wendougee_data.const import DOMAIN
from custom_components.wendougee_data.coordinator import WendougeeCoordinator
from tests.test_reads import register_response

from .test_integration import BASELINE_FRAMES, CONFIGURATION_VALUES, TELEMETRY, entry

pytestmark = pytest.mark.asyncio


async def test_default_entry_cannot_call_controls(hass):
    coordinator = WendougeeCoordinator(hass, entry())
    with patch(f"custom_components.{DOMAIN}.coordinator.execute_boiler") as execute:
        with pytest.raises(HomeAssistantError, match="not enabled"):
            await coordinator.async_set_boiler(BoilerSetting.BREW_ENABLED, True)
        with pytest.raises(HomeAssistantError, match="not enabled"):
            await coordinator.async_start_profile()
        execute.assert_not_called()


async def test_opt_in_registers_switches_and_button_without_control_on_setup(hass):
    configured = entry()
    configured.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        configured,
        options={
            "allow_boiler_control": True,
            "allow_profile_start": True,
        },
    )
    with (
        patch(
            f"custom_components.{DOMAIN}.coordinator.read_baseline",
            return_value=BASELINE_FRAMES,
        ),
        patch(
            f"custom_components.{DOMAIN}.coordinator.execute_boiler",
            new_callable=AsyncMock,
        ) as boiler,
        patch(
            f"custom_components.{DOMAIN}.coordinator.execute_profile",
            new_callable=AsyncMock,
        ) as profile,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        states = hass.states.async_all()
        assert (
            len([s for s in states if s.entity_id.startswith("switch.wendougee")]) == 2
        )
        assert (
            len([s for s in states if s.entity_id.startswith("button.wendougee")]) == 1
        )
        boiler.assert_not_called()
        profile.assert_not_called()
        await hass.config_entries.async_unload(configured.entry_id)


async def test_boiler_updates_only_after_readback(hass):
    configured = entry()
    configured.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        configured, options={"allow_boiler_control": True}
    )
    coordinator = WendougeeCoordinator(hass, configured)
    coordinator.data = TELEMETRY
    words = list(CONFIGURATION_VALUES)
    words[6] = 0
    configuration = decode_configuration(register_response(words))
    with patch(
        f"custom_components.{DOMAIN}.coordinator.execute_boiler",
        return_value=configuration,
    ) as execute:
        await coordinator.async_set_boiler(BoilerSetting.STEAM_ENABLED, True)
    assert coordinator.configuration.steam_heating_enabled is True
    execute.assert_awaited_once()


async def test_uncertain_start_is_persisted_and_blocks_repeat_after_reload(hass):
    configured = entry()
    configured.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        configured, options={"allow_profile_start": True}
    )
    coordinator = WendougeeCoordinator(hass, configured)
    with patch(
        f"custom_components.{DOMAIN}.coordinator.execute_profile",
        side_effect=TimeoutError("private-address"),
    ) as execute:
        with pytest.raises(HomeAssistantError, match="uncertain") as error:
            await coordinator.async_start_profile()
        assert "private-address" not in str(error.value)
        restored = WendougeeCoordinator(hass, configured)
        await restored.async_load_control_state()
        assert restored.profile_start_locked
        with pytest.raises(HomeAssistantError, match="uncertain"):
            await restored.async_start_profile()
        assert execute.await_count == 1


async def test_profile_request_does_not_queue_behind_other_operations(hass):
    configured = entry()
    configured.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        configured, options={"allow_profile_start": True}
    )
    coordinator = WendougeeCoordinator(hass, configured)
    async with coordinator._connection_lock:
        with pytest.raises(HomeAssistantError, match="busy"):
            await coordinator.async_start_profile()


async def test_failed_storage_clear_keeps_start_locked(hass):
    coordinator = WendougeeCoordinator(hass, entry())
    coordinator.profile_start_locked = True
    with (
        patch.object(coordinator._control_store, "async_save", side_effect=OSError),
        pytest.raises(OSError),
    ):
        await coordinator._save_profile_lock(False)
    assert coordinator.profile_start_locked


async def test_options_flow_exposes_separate_control_opt_ins(hass):
    configured = entry()
    configured.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(configured.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"allow_boiler_control": True, "allow_profile_start": False},
    )
    assert result["type"] == "create_entry"
    assert configured.options == {
        "allow_boiler_control": True,
        "allow_profile_start": False,
    }


async def test_transport_rejects_writes_outside_transaction_allowlist(hass):
    from custom_components.wendougee_data._protocol.control_session import (
        Command,
        command_request,
    )
    from custom_components.wendougee_data.control import HomeAssistantControlTransport

    transport = HomeAssistantControlTransport(
        hass, "00:11:22:33:44:55", frozenset({Command.BREW_ON})
    )
    transport.client = AsyncMock()
    for command in (Command.STEAM_ON, Command.PROFILE_PRESS, Command.BREW_OFF):
        with pytest.raises(ValueError, match="not enabled"):
            await transport.send(command_request(command))
    transport.client.write_gatt_char.assert_not_called()
