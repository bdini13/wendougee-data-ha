"""Explicit boiler-enable and stored-profile transactions, without retries.

Only mode 2 of the already selected active profile is accepted. No profile,
setpoint, mode selector, cleaning command or arbitrary address is writable.
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


class Command(Enum):
    CONFIGURATION = (3, 0, 37)
    TELEMETRY = (3, 1404, 22)
    STATE = (1, 182, 24)
    PROFILE_MODE = (3, 87, 1)
    STEAM_ON = (6, 6, 0)
    STEAM_OFF = (6, 6, 1)
    BREW_ON = (6, 7, 0)
    BREW_OFF = (6, 7, 1)
    PROFILE_PRESS = (5, 150, 0xFF00)
    PROFILE_RELEASE = (5, 150, 0)


def command_request(command: Command) -> bytes:
    """Build only the finite request set; accept no caller-supplied address/value."""
    if not isinstance(command, Command):
        raise ValueError("Unknown control-session command")
    function, address, value = command.value
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
            payload_size = (count + 7) // 8 if function == 1 else count * 2
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
        async with asyncio.timeout(3):
            if self._failure is None:
                await self.transact(Command.PROFILE_RELEASE)
            else:
                await self._transport.send(command_request(Command.PROFILE_RELEASE))


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
