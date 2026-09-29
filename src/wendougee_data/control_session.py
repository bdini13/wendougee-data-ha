"""Explicit boiler-enable and stored-profile transactions, without retries.

Profile pilot accepts only the observed one-stage 9 bar / 28 s / 65 mL recipe.
Preparation and activation are separate; no binding, selector or arbitrary write.
"""

import asyncio
from enum import Enum

from .controls import BoilerSetting, build_boiler_setting_request
from .crc import append_crc, crc16_modbus
from .reads import DeviceException, ReadOperation
from .session import ReadSession
from .state import (
    Configuration,
    OperatingState,
    decode_configuration,
    decode_operating_state,
)
from .telemetry import parse_telemetry_response


class ControlRejected(ValueError):
    """A fresh precondition failed before any machine control was attempted."""


def failure_kind(error: Exception) -> str:
    """Finite privacy-safe categories; never expose backend exception text."""
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, DeviceException):
        return "device_exception"
    if isinstance(error, ValueError):
        return "protocol_or_validation"
    return "transport_or_internal"


class Command(Enum):
    CONFIGURATION = (3, 0, 37)
    TELEMETRY = (3, 1404, 22)
    STATE = (1, 182, 24)
    PROFILE_MODE = (3, 87, 1)
    PROFILE_MODES = (3, 87, 2)
    ACTIVE_HEAD = (3, 2048, 125)
    ACTIVE_TAIL = (3, 2173, 42)
    BOUND_HEAD = (3, 2560, 125)
    BOUND_TAIL = (3, 2685, 42)
    PILOT_HEADER = (16, 2048, (1, 1, 1, 1, 65, 0, 0))
    PILOT_STAGE = (16, 2056, (28, 90, 0, 0, 1, 0))
    STEAM_ON = (6, 6, 0)
    STEAM_OFF = (6, 6, 1)
    BREW_ON = (6, 7, 0)
    BREW_OFF = (6, 7, 1)
    PROFILE_PRESS = (5, 150, 0xFF00)
    PROFILE_RELEASE = (5, 150, 0)
    CLEANING_PRESS = (5, 155, 0xFF00)
    CLEANING_RELEASE = (5, 155, 0)


def command_request(command: Command) -> bytes:
    """Build only the finite request set; accept no caller-supplied address/value."""
    if not isinstance(command, Command):
        raise ValueError("Unknown control-session command")
    function, address, value = command.value
    if function == 16:
        return append_crc(
            bytes((1, 16))
            + address.to_bytes(2, "big")
            + len(value).to_bytes(2, "big")
            + bytes((2 * len(value),))
            + b"".join(word.to_bytes(2, "big") for word in value)
        )
    return append_crc(
        bytes((1, function)) + address.to_bytes(2, "big") + value.to_bytes(2, "big")
    )


class ControlSession(ReadSession):
    """Reuse bounded lifecycle/quarantine, validating exact command responses."""

    def __init__(self, transport, *, timeout=15.0):
        super().__init__(transport, timeout=timeout)
        self._command_buffer = bytearray()

    async def transact(self, command: Command) -> bytes:
        return await self._exchange(command_request(command), command)

    def _on_data(self, fragment: bytes) -> None:
        if isinstance(self._operation, ReadOperation):
            super()._on_data(fragment)
            return
        if not fragment or self._failure is not None:
            return
        pending = self._pending
        if (
            pending is None
            or pending.done()
            or not isinstance(self._operation, Command)
        ):
            self._invalidate(ValueError("Unsolicited or duplicate command response"))
            return
        try:
            self._command_buffer.extend(fragment)
            frame = bytes(self._command_buffer)
            if len(frame) < 2:
                return
            function, _, count = self._operation.value
            exception = frame[1] == function | 0x80
            if frame[0] != 1 or frame[1] not in (function, function | 0x80):
                raise ValueError("Unexpected control response identity")
            payload_size = (
                ((count + 7) // 8 if function == 1 else count * 2)
                if function in (1, 3)
                else 0
            )
            length = 5 if exception else (payload_size + 5 if function in (1, 3) else 8)
            if len(frame) > length:
                raise ValueError("Extra command response bytes")
            if len(frame) < length:
                return
            if crc16_modbus(frame[:-2]) != int.from_bytes(frame[-2:], "little"):
                raise ValueError("Control response CRC mismatch")
            if exception:
                raise DeviceException(frame[2])
            if function in (5, 6):
                if frame != command_request(self._operation):
                    raise ValueError("Control response echo mismatch")
            elif function == 16:
                if frame != append_crc(command_request(self._operation)[:6]):
                    raise ValueError("Profile write echo mismatch")
            elif frame[2] != payload_size:
                raise ValueError("Control response byte count mismatch")
        except ValueError as error:
            self._invalidate(error)
        else:
            self._command_buffer.clear()
            pending.set_result(frame)

    async def release_profile_press(self) -> None:
        """Deassert once even if the press acknowledgement became uncertain.

        A quarantined connection cannot validate another response. In that case
        only a best-effort release is sent; the original error remains an error.
        This is cleanup, never another press or a retry of an uncertain action.
        """
        await self.release_press(Command.PROFILE_RELEASE)

    async def release_press(self, command: Command) -> None:
        """Deassert only a known momentary input, even after quarantine."""
        if command not in (Command.PROFILE_RELEASE, Command.CLEANING_RELEASE):
            raise ValueError("Only a momentary release is allowed")
        async with asyncio.timeout(3):
            if self._failure is None:
                await self.transact(command)
            else:
                await self._transport.send(command_request(command))


async def _idle(session: ControlSession) -> OperatingState:
    state = decode_operating_state(await session.transact(Command.STATE))
    if state.state != "idle":
        raise ControlRejected("Machine must be idle with no unknown operating flags")
    return state


async def set_boiler(
    session: ControlSession, setting: BoilerSetting, enabled: bool
) -> Configuration:
    """Read before write, preserve all other settings, and verify full readback."""
    if setting not in (BoilerSetting.STEAM_ENABLED, BoilerSetting.BREW_ENABLED):
        raise ControlRejected("Only boiler enable settings are supported")
    request = build_boiler_setting_request(setting, enabled)
    before = decode_configuration(await session.transact(Command.CONFIGURATION))
    await _idle(session)
    if before.raw_registers[setting.register] not in (0, 1):
        raise ControlRejected("Unknown boiler enable encoding")
    if before.raw_registers[setting.register] == (0 if enabled else 1):
        return before
    if enabled:
        telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
        if telemetry.water_level_alarm:
            raise ControlRejected("Water shortage alarm is active")
        await _idle(session)
    command = next(c for c in Command if command_request(c) == request)
    await session.transact(command)
    after = decode_configuration(await session.transact(Command.CONFIGURATION))
    expected = list(before.raw_registers)
    expected[setting.register] = 0 if enabled else 1
    if after.raw_registers != tuple(expected):
        raise ValueError("Boiler configuration readback mismatch")
    return after


async def start_stored_profile(session: ControlSession) -> OperatingState:
    """Pulse the existing active mode-2 profile once, then verify profile state.

    Coil 150 is a toggle. Busy states are rejected, no stop action is inferred,
    and callers must persist an uncertainty latch before entering this function.
    """
    configuration = decode_configuration(await session.transact(Command.CONFIGURATION))
    if configuration.brew_heating_enabled is not True:
        raise ControlRejected("Brew boiler must already be enabled")
    telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
    if telemetry.water_level_alarm:
        raise ControlRejected("Water shortage alarm is active")
    mode = await session.transact(Command.PROFILE_MODE)
    if int.from_bytes(mode[3:5], "big") != 2:
        raise ControlRejected(
            "Only an already selected stored mode-2 profile is supported"
        )
    validate_pilot(await read_profile_bank(session, bound=False))
    await _idle(session)
    try:
        await session.transact(Command.PROFILE_PRESS)
        await asyncio.sleep(0.1)
    finally:
        # Cleanup must finish before session exit disconnects the transport.
        release = asyncio.create_task(session.release_profile_press())
        try:
            await asyncio.shield(release)
        except asyncio.CancelledError:
            await release
            raise
    for _ in range(5):
        state = decode_operating_state(await session.transact(Command.STATE))
        if state.state == "profile":
            return state
        if state.state != "idle":
            raise ValueError("Unexpected state after profile pulse")
        await asyncio.sleep(0.2)
    raise ValueError("Profile start was not confirmed; do not repeat the pulse")


def _registers(frame: bytes) -> tuple[int, ...]:
    return tuple(
        int.from_bytes(frame[i : i + 2], "big") for i in range(3, len(frame) - 2, 2)
    )


async def read_profile_bank(session: ControlSession, *, bound: bool) -> tuple[int, ...]:
    """Read the documented 167-word bank in two legal FC03 chunks."""
    commands = (
        (Command.BOUND_HEAD, Command.BOUND_TAIL)
        if bound
        else (Command.ACTIVE_HEAD, Command.ACTIVE_TAIL)
    )
    return _registers(await session.transact(commands[0])) + _registers(
        await session.transact(commands[1])
    )


async def audit_profile_reads(session: ControlSession) -> dict:
    """One bounded diagnostic, stopping on first failure; no writes or retries."""
    frames = {}
    commands = (
        Command.STATE,
        Command.PROFILE_MODES,
        Command.ACTIVE_HEAD,
        Command.ACTIVE_TAIL,
        Command.BOUND_HEAD,
        Command.BOUND_TAIL,
    )
    for command in commands:
        try:
            frames[command] = await session.transact(command)
            if (
                command == Command.STATE
                and decode_operating_state(frames[command]).state != "idle"
            ):
                raise ControlRejected("Machine is not idle")
        except Exception as error:
            return {
                "read_only": True,
                "successful": False,
                "stage": command.name.lower(),
                "failure_kind": failure_kind(error),
            }
    return {
        "read_only": True,
        "successful": True,
        "stage": "complete",
        "failure_kind": None,
        "active_words": len(_registers(frames[Command.ACTIVE_HEAD]))
        + len(_registers(frames[Command.ACTIVE_TAIL])),
        "bound_words": len(_registers(frames[Command.BOUND_HEAD]))
        + len(_registers(frames[Command.BOUND_TAIL])),
    }


def validate_pilot(bank: tuple[int, ...]) -> None:
    """No generalized recipe interpretation: match the attended pilot exactly."""
    if (
        len(bank) != 167
        or bank[:7] != Command.PILOT_HEADER.value[2]
        or bank[8:14] != Command.PILOT_STAGE.value[2]
    ):
        raise ControlRejected("Stored profile is not the verified 9 bar pilot recipe")


async def prepare_pilot_profile(session: ControlSession, backup) -> dict:
    """Copy only the exact known recipe into active storage, never activate.

    Caller durably locks controls first. Backup must complete before any write.
    No rollback/retry after uncertainty; full banks and configuration are checked.
    """
    await _idle(session)
    config = await session.transact(Command.CONFIGURATION)
    telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
    if telemetry.water_level_alarm:
        raise ControlRejected("Water shortage alarm is active")
    modes = await session.transact(Command.PROFILE_MODES)
    if _registers(modes) != (2, 2):
        raise ControlRejected("Both profile selectors must already be mode 2")
    active = await read_profile_bank(session, bound=False)
    bound = await read_profile_bank(session, bound=True)
    validate_pilot(bound)
    await backup(
        {
            "active": active,
            "bound": bound,
            "configuration": _registers(config),
            "modes": (2, 2),
        }
    )
    # Recheck every backed-up word after storage I/O and immediately before writes.
    if (
        active != await read_profile_bank(session, bound=False)
        or bound != await read_profile_bank(session, bound=True)
        or modes != await session.transact(Command.PROFILE_MODES)
        or config != await session.transact(Command.CONFIGURATION)
    ):
        raise ControlRejected("Profile or configuration changed before preparation")
    await _idle(session)
    expected = list(active)
    expected[:7] = Command.PILOT_HEADER.value[2]
    expected[8:14] = Command.PILOT_STAGE.value[2]
    writes = 0
    if tuple(expected) != active:
        # Terminal stage first; header last. No selector or binding changes.
        await session.transact(Command.PILOT_STAGE)
        writes += 1
        await session.transact(Command.PILOT_HEADER)
        writes += 1
    after = await read_profile_bank(session, bound=False)
    unchanged = await read_profile_bank(session, bound=True)
    if (
        after != tuple(expected)
        or unchanged != bound
        or modes != await session.transact(Command.PROFILE_MODES)
        or config != await session.transact(Command.CONFIGURATION)
    ):
        raise ValueError("Profile preparation full readback mismatch; do not retry")
    state = decode_operating_state(await session.transact(Command.STATE))
    if state.state != "idle":
        raise ValueError("Machine left idle during preparation")
    return {
        "prepared": True,
        "started": False,
        "write_count": writes,
        "bound_bank_unchanged": True,
        "configuration_unchanged": True,
        "target_ml": 65,
        "pressure_bar": 9,
        "stage_seconds": 28,
    }
