"""Short, explicitly requested control sessions on HA's shared Bluetooth route."""

import asyncio

from homeassistant.core import HomeAssistant

from ._protocol.cleaning import cleaning_duration, start_cleaning
from ._protocol.control_session import (
    Command,
    ControlRejected,
    ControlSession,
    command_request,
    set_boiler,
    start_stored_profile,
)
from ._protocol.controls import BoilerSetting, build_boiler_setting_request
from ._protocol.state import decode_configuration, decode_operating_state
from ._protocol.telemetry import parse_telemetry_response
from .bluetooth import HomeAssistantReadTransport

READ_COMMANDS = frozenset({Command.CONFIGURATION, Command.TELEMETRY, Command.STATE})


class HomeAssistantControlTransport(HomeAssistantReadTransport):
    """An explicit finite allowlist, separate from every existing read transport."""

    def __init__(self, hass, address, commands: frozenset[Command]):
        super().__init__(hass, address)
        self._requests = frozenset(command_request(c) for c in commands)

    async def send(self, request: bytes) -> None:
        if request not in self._requests:
            raise ValueError("Request is not enabled for this control transaction")
        if self.client is None or self.modbus is None:
            raise ConnectionError("Transport not ready")
        await self.client.write_gatt_char(
            self.modbus,
            request,
            response="write-without-response" not in self.modbus.properties,
        )


async def execute_boiler(hass: HomeAssistant, address, setting, enabled):
    if setting not in (BoilerSetting.STEAM_ENABLED, BoilerSetting.BREW_ENABLED):
        raise ControlRejected("Only boiler enable settings are supported")
    request = build_boiler_setting_request(setting, enabled)
    write = next(c for c in Command if command_request(c) == request)
    transport = HomeAssistantControlTransport(hass, address, READ_COMMANDS | {write})
    async with ControlSession(transport) as session:
        return await set_boiler(session, setting, enabled)


async def execute_profile(hass: HomeAssistant, address):
    commands = READ_COMMANDS | {
        Command.PROFILE_MODE,
        Command.PROFILE_PRESS,
        Command.PROFILE_RELEASE,
    }
    transport = HomeAssistantControlTransport(hass, address, commands)
    async with ControlSession(transport) as session:
        state = await start_stored_profile(session)
        telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
        return telemetry, state


async def verify_idle(hass: HomeAssistant, address):
    transport = HomeAssistantControlTransport(hass, address, frozenset({Command.STATE}))
    async with ControlSession(transport) as session:
        state = decode_operating_state(await session.transact(Command.STATE))
        if state.state != "idle":
            raise ControlRejected(
                "Machine must report idle before clearing uncertainty"
            )


async def execute_cleaning(hass: HomeAssistant, address, observe):
    """Keep one connection through the stored program, observing without retries.

    A return to idle is evidence of state, not proof of cleaning effectiveness
    or that every programmed repetition physically ran. Never send a stop toggle.
    """
    commands = READ_COMMANDS | {Command.CLEANING_PRESS, Command.CLEANING_RELEASE}
    transport = HomeAssistantControlTransport(hass, address, commands)
    async with ControlSession(transport) as session:
        configuration, state = await start_cleaning(session)
        duration = cleaning_duration(configuration)
        # Preserve the confirmed start even if a short program ends before the
        # next state read. Telemetry and state reads are not atomic snapshots.
        telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
        observe(telemetry, state, configuration)
        loop = asyncio.get_running_loop()
        started = loop.time()
        idle_samples = 0
        sample_count = 1
        pressure_max = telemetry.pressure_bar
        states = {"cleaning"}
        async with asyncio.timeout(duration + 20):
            while True:
                telemetry = parse_telemetry_response(
                    await session.transact(Command.TELEMETRY)
                )
                state = decode_operating_state(await session.transact(Command.STATE))
                if (
                    state.state not in ("cleaning", "idle")
                    or telemetry.water_level_alarm
                ):
                    raise ValueError("Unexpected state or water alarm during cleaning")
                observe(telemetry, state, configuration)
                sample_count += 1
                pressure_max = max(pressure_max, telemetry.pressure_bar)
                states.add(state.state)
                idle_samples = idle_samples + 1 if state.state == "idle" else 0
                elapsed = loop.time() - started
                if elapsed >= duration and idle_samples >= 2:
                    after = decode_configuration(
                        await session.transact(Command.CONFIGURATION)
                    )
                    if after.raw_registers != configuration.raw_registers:
                        raise ValueError(
                            "Cleaning configuration changed during observation"
                        )
                    return {
                        "schema": "wendougee-data-cleaning-result/v1",
                        "result": "cleaning_observed_then_idle",
                        "cleaning_time_seconds": configuration.cleaning_time_seconds,
                        "standing_time_seconds": configuration.cleaning_rest_seconds,
                        "cleaning_count": configuration.cleaning_repetitions,
                        "settings_unchanged": True,
                        "observed_seconds": elapsed,
                        "sample_count": sample_count,
                        "peak_pressure_bar": pressure_max,
                        "observed_states": sorted(states | {"cleaning"}),
                    }
                await asyncio.sleep(0.5)
