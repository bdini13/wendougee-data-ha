"""Synthetic control transactions: exact echoes, guards and uncertain outcomes."""

import asyncio
from functools import wraps

import pytest

from wendougee_data.control_session import (
    Command,
    ControlRejected,
    ControlSession,
    audit_profile_reads,
    command_request,
    prepare_pilot_profile,
    read_profile_bank,
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


@run_async
async def test_control_bank_reader_uses_verified_chunks_and_keeps_last_word():
    machine = Machine()
    machine.active[-1] = 123
    machine.bound[-1] = 456
    async with ControlSession(machine) as session:
        assert await read_profile_bank(session, bound=False) == tuple(machine.active)
        assert await read_profile_bank(session, bound=True) == tuple(machine.bound)
    assert len(machine.sent) == 22
    assert all(r[1] == 3 and int.from_bytes(r[4:6], "big") <= 16 for r in machine.sent)


@run_async
async def test_profile_audit_is_read_only_and_reports_exact_failed_step():
    from unittest.mock import AsyncMock

    session = AsyncMock()
    session.transact.side_effect = TimeoutError("private address and packet")
    result = await audit_profile_reads(session)
    assert result == {
        "read_only": True,
        "successful": False,
        "stage": "state",
        "failure_kind": "timeout",
    }
    session.transact.assert_awaited_once_with(Command.STATE)


@run_async
async def test_profile_audit_complete_banks_without_any_control():
    machine = Machine()
    async with ControlSession(machine) as session:
        result = await audit_profile_reads(session)
    assert result["successful"]
    assert result["active_words"] == result["bound_words"] == 167
    assert all(request[1] in (1, 3) for request in machine.sent)
    bank_requests = [
        r for r in machine.sent if r[1] == 3 and int.from_bytes(r[2:4], "big") >= 2048
    ]
    assert max(int.from_bytes(r[4:6], "big") for r in bank_requests) <= 16
    assert result["repeat_matched"]


@run_async
async def test_chunk_audit_rejects_changed_last_word():
    class ChangingMachine(Machine):
        async def send(self, request):
            if request == command_request(Command.BOUND_CHUNK_10):
                self.bound[-1] += 1
            await super().send(request)

    machine = ChangingMachine()
    async with ControlSession(machine) as session:
        result = await audit_profile_reads(session)
    assert result["stage"] == "bound_chunk_10"
    assert result["failure_kind"] == "readback_changed"
    assert all(r[1] in (1, 3) for r in machine.sent)


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
        self.active = [0] * 167
        self.active[:7] = [1, 1, 1, 1, 65, 0, 0]
        self.active[8:14] = [28, 90, 0, 0, 1, 0]
        self.bound = self.active.copy()
        self.corrupt_bound_on_upload = False

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
        elif fc == 16:
            start = int.from_bytes(request[2:4], "big") - 2048
            words = [
                int.from_bytes(request[i : i + 2], "big")
                for i in range(7, len(request) - 2, 2)
            ]
            self.active[start : start + len(words)] = words
            if self.corrupt_bound_on_upload:
                self.bound[166] += 1
            reply = append_crc(request[:6])
            if self.bad_echo:
                reply = append_crc(request[:5] + b"\x01")
        elif fc == 5:
            if request[4] == 255 and self.drop_press:
                return
            if request[4] == 0:
                self.bits = 1
            reply = request
        elif fc == 1:
            reply = append_crc(b"\x01\x01\x03" + self.bits.to_bytes(3, "little"))
        elif 2048 <= int.from_bytes(request[2:4], "big") <= 2726:
            address = int.from_bytes(request[2:4], "big")
            bank, base = (self.active, 2048) if address < 2560 else (self.bound, 2560)
            count = int.from_bytes(request[4:6], "big")
            reply = register_response(bank[address - base : address - base + count])
        elif request[2:4] == b"\x00\x57":
            count = int.from_bytes(request[4:6], "big")
            reply = register_response([self.mode] * count)
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
async def test_empty_active_profile_never_starts_despite_mode_two():
    machine = Machine()
    machine.words[7] = 0
    machine.active = [0] * 167
    async with ControlSession(machine) as session:
        with pytest.raises(ControlRejected, match="profile"):
            await start_stored_profile(session)
    assert all(r[1] in (1, 3) for r in machine.sent)


@run_async
async def test_prepare_backs_up_full_banks_and_never_activates():
    machine = Machine()
    machine.active = [0] * 167
    machine.split = True
    backups = []

    async def backup(document):
        assert all(r[1] in (1, 3) for r in machine.sent)
        backups.append(document)

    async with ControlSession(machine) as session:
        result = await prepare_pilot_profile(session, backup)
    assert result["started"] is False
    assert result["write_count"] == 2
    assert len(backups[0]["active"]) == len(backups[0]["bound"]) == 167
    assert machine.active == machine.bound
    assert [r for r in machine.sent if r[1] not in (1, 3)] == [
        command_request(Command.PILOT_STAGE),
        command_request(Command.PILOT_HEADER),
    ]


@run_async
@pytest.mark.parametrize("failure", ["backup", "bound", "echo", "readback"])
async def test_prepare_fails_closed_without_start_or_retry(failure):
    machine = Machine()
    machine.active = [0] * 167
    machine.bad_echo = failure == "echo"
    machine.corrupt_bound_on_upload = failure == "readback"
    if failure == "bound":
        machine.bound[9] = 150

    async def backup(document):
        if failure == "backup":
            raise OSError("Storage failed")

    async with ControlSession(machine) as session:
        with pytest.raises((OSError, ValueError)):
            await prepare_pilot_profile(session, backup)
    assert not any(r[1] in (5, 6) for r in machine.sent)
    assert len([r for r in machine.sent if r[1] == 16]) == (
        1 if failure == "echo" else 2 if failure == "readback" else 0
    )


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
    assert {int.from_bytes(r[2:4], "big") for r in requests if r[1] == 5} == {150, 155}
    with pytest.raises(ValueError):
        command_request("arbitrary")
