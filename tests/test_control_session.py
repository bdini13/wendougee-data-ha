"""Synthetic control transactions: exact echoes, guards and uncertain outcomes."""

import asyncio
from functools import wraps

import pytest

from wendougee_data.control_session import (
    Command,
    ControlRejected,
    ControlSession,
    command_request,
    set_boiler,
    start_stored_profile,
)
from wendougee_data.controls import BoilerSetting
from wendougee_data.crc import append_crc
from wendougee_data.session import SessionUnavailable

from .test_reads import register_response


def run_async(test):
    @wraps(test)
    def run(*args, **kwargs):
        return asyncio.run(test(*args, **kwargs))

    return run


class Machine:
    def __init__(self):
        self.words = [0] * 37
        self.words[6:10] = [1, 1, 126, 92]
        self.bits = 0
        self.mode = 2
        self.sent = []
        self.closed = False
        self.bad_echo = False
        self.drop_press = False
        self.unrelated_change = False
        self.split = False
        self.alarm = False

    async def open(self, on_data, on_disconnect):
        self.on_data = on_data
        self.on_disconnect = on_disconnect

    async def close(self):
        self.closed = True

    async def send(self, request):
        self.sent.append(request)
        fc = request[1]
        if fc == 6:
            self.words[int.from_bytes(request[2:4], "big")] = int.from_bytes(
                request[4:6], "big"
            )
            if self.unrelated_change:
                self.words[8] += 1
            reply = request if not self.bad_echo else append_crc(request[:5] + b"\x02")
        elif fc == 5:
            if request[4] == 255 and self.drop_press:
                return
            if request[4] == 0:
                self.bits = 1
            reply = request
        elif fc == 1:
            reply = append_crc(b"\x01\x01\x03" + self.bits.to_bytes(3, "little"))
        elif request[2:4] == b"\x00\x57":
            reply = register_response([self.mode])
        elif request[2:4] == b"\x00\x00":
            reply = register_response(self.words)
        else:
            words = [0] * 22
            words[2] = int(self.alarm)
            reply = register_response(words)
        if self.split:
            for value in reply:
                self.on_data(bytes([value]))
        else:
            self.on_data(reply)


@run_async
@pytest.mark.parametrize(
    "setting", [BoilerSetting.STEAM_ENABLED, BoilerSetting.BREW_ENABLED]
)
async def test_boiler_checks_full_configuration_and_noops_when_already_set(setting):
    machine = Machine()
    machine.split = True
    async with ControlSession(machine, timeout=0.1) as session:
        result = await set_boiler(session, setting, True)
        assert result.raw_registers[setting.register] == 0
        await set_boiler(session, setting, True)
    assert len([r for r in machine.sent if r[1] == 6]) == 1
    assert machine.closed


@run_async
@pytest.mark.parametrize("bits", [1, 16, 32, 0x800, 0x4000, 17])
async def test_busy_or_unknown_state_never_changes_boilers(bits):
    machine = Machine()
    machine.bits = bits
    async with ControlSession(machine) as session:
        with pytest.raises(ControlRejected):
            await set_boiler(session, BoilerSetting.BREW_ENABLED, True)
    assert all(r[1] in (1, 3) for r in machine.sent)


@run_async
async def test_unrelated_setting_change_fails_readback():
    machine = Machine()
    machine.unrelated_change = True
    async with ControlSession(machine) as session:
        with pytest.raises(ValueError, match="readback"):
            await set_boiler(session, BoilerSetting.BREW_ENABLED, True)


@run_async
async def test_wrong_echo_quarantines_session_without_retry():
    machine = Machine()
    machine.bad_echo = True
    async with ControlSession(machine) as session:
        with pytest.raises(ValueError):
            await set_boiler(session, BoilerSetting.BREW_ENABLED, True)
        with pytest.raises(SessionUnavailable):
            await session.transact(Command.CONFIGURATION)
    assert len([r for r in machine.sent if r[1] == 6]) == 1


@run_async
async def test_stored_profile_pulses_only_coil_150_and_verifies_state():
    machine = Machine()
    machine.words[7] = 0
    async with ControlSession(machine) as session:
        state = await start_stored_profile(session)
    assert state.state == "profile"
    assert [r.hex() for r in machine.sent if r[1] == 5] == [
        "01050096ff006c16",
        "0105009600002de6",
    ]
    assert not any(r[1] in (6, 16) for r in machine.sent)


@run_async
@pytest.mark.parametrize("mode", [0, 1, 3, 4, 65535])
async def test_unverified_profile_modes_never_pulse(mode):
    machine = Machine()
    machine.mode = mode
    machine.words[7] = 0
    async with ControlSession(machine) as session:
        with pytest.raises(ControlRejected):
            await start_stored_profile(session)
    assert all(r[1] in (1, 3) for r in machine.sent)


@run_async
async def test_uncertain_press_is_released_once_and_never_retried():
    machine = Machine()
    machine.words[7] = 0
    machine.drop_press = True
    async with ControlSession(machine, timeout=0.01) as session:
        with pytest.raises(TimeoutError):
            await start_stored_profile(session)
    writes = [r for r in machine.sent if r[1] == 5]
    assert writes == [
        command_request(Command.PROFILE_PRESS),
        command_request(Command.PROFILE_RELEASE),
    ]


@run_async
async def test_cancellation_after_press_releases_before_disconnect():
    machine = Machine()
    machine.words[7] = 0
    async with ControlSession(machine) as session:
        task = asyncio.create_task(start_stored_profile(session))
        while command_request(Command.PROFILE_PRESS) not in machine.sent:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert machine.sent[-1] == command_request(Command.PROFILE_RELEASE)


@run_async
@pytest.mark.parametrize("condition", ["boiler_off", "alarm", "busy", "unknown"])
async def test_profile_preconditions_prevent_any_control_write(condition):
    machine = Machine()
    machine.words[7] = 1 if condition == "boiler_off" else 0
    machine.alarm = condition == "alarm"
    machine.bits = {"busy": 1, "unknown": 0x4000}.get(condition, 0)
    async with ControlSession(machine) as session:
        with pytest.raises(ControlRejected):
            await start_stored_profile(session)
    assert all(r[1] in (1, 3) for r in machine.sent)


@run_async
async def test_water_alarm_blocks_boiler_on():
    machine = Machine()
    machine.alarm = True
    async with ControlSession(machine) as session:
        with pytest.raises(ControlRejected, match="alarm"):
            await set_boiler(session, BoilerSetting.BREW_ENABLED, True)
    assert all(r[1] in (1, 3) for r in machine.sent)


@run_async
@pytest.mark.parametrize("fault", ["crc", "exception", "trailing", "duplicate"])
async def test_control_reply_faults_quarantine_without_retry(fault):
    class Faulty(Machine):
        async def send(self, request):
            self.sent.append(request)
            if fault == "crc":
                self.on_data(request[:-1] + bytes([request[-1] ^ 1]))
            elif fault == "exception":
                self.on_data(append_crc(bytes([1, request[1] | 0x80, 2])))
            elif fault == "trailing":
                self.on_data(request + b"\x00")
            else:
                self.on_data(request)
                self.on_data(request)

    machine = Faulty()
    async with ControlSession(machine) as session:
        with pytest.raises((ValueError, SessionUnavailable)):
            await session.transact(Command.BREW_ON)
        with pytest.raises(SessionUnavailable):
            await session.transact(Command.BREW_ON)
    assert len(machine.sent) == 1


def test_commands_exclude_temperature_profile_upload_and_arbitrary_addresses():
    requests = [command_request(c) for c in Command]
    assert {int.from_bytes(r[2:4], "big") for r in requests if r[1] == 6} == {6, 7}
    assert {int.from_bytes(r[2:4], "big") for r in requests if r[1] == 5} == {150}
    with pytest.raises(ValueError):
        command_request("arbitrary")
