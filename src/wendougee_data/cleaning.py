"""Start the stored cleaning program, never upload or alter its parameters."""

import asyncio

from .control_session import Command, ControlRejected, ControlSession
from .state import (
    Configuration,
    OperatingState,
    decode_configuration,
    decode_operating_state,
)
from .telemetry import parse_telemetry_response


def cleaning_duration(configuration: Configuration) -> float:
    """Pilot envelope, not a claim about manufacturer-supported limits.

    Include the final standing interval as a conservative observation budget.
    Reject unsupported programs rather than silently replacing their settings.
    """
    run = configuration.cleaning_time_seconds
    rest = configuration.cleaning_rest_seconds
    count = configuration.cleaning_repetitions
    duration = (run + rest) * count
    if not (
        1 <= run <= 60 and 1 <= rest <= 60 and 1 <= count <= 10 and duration <= 120
    ):
        raise ControlRejected(
            "Stored cleaning program is outside the attended pilot envelope "
            "(maximum 120 seconds)"
        )
    return duration


async def start_cleaning(
    session: ControlSession,
) -> tuple[Configuration, OperatingState]:
    """One guarded pulse, exact echoes, unchanged config and observed cleaning."""
    before = decode_configuration(await session.transact(Command.CONFIGURATION))
    cleaning_duration(before)
    if before.brew_heating_enabled is not True:
        raise ControlRejected("Brew boiler must already be enabled")
    telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
    if telemetry.water_level_alarm:
        raise ControlRejected("Water shortage alarm is active")
    state = decode_operating_state(await session.transact(Command.STATE))
    if state.state != "idle":
        raise ControlRejected("Machine must be idle with no unknown operating flags")
    try:
        await session.transact(Command.CLEANING_PRESS)
        await asyncio.sleep(0.1)
    finally:
        release = asyncio.create_task(session.release_press(Command.CLEANING_RELEASE))
        try:
            await asyncio.shield(release)
        except asyncio.CancelledError:
            await release
            raise
    after = decode_configuration(await session.transact(Command.CONFIGURATION))
    if after.raw_registers != before.raw_registers:
        raise ValueError("Cleaning configuration changed unexpectedly")
    for _ in range(5):
        state = decode_operating_state(await session.transact(Command.STATE))
        if state.state == "cleaning":
            return before, state
        if state.state != "idle":
            raise ValueError("Unexpected operating state after cleaning pulse")
        await asyncio.sleep(0.2)
    raise ValueError("Cleaning start was not confirmed; do not repeat the pulse")
