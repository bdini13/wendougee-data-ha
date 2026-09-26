"""Synthetic cleaning activation; preserve the stored program and never retry."""

import asyncio

import pytest

from wendougee_data.cleaning import start_cleaning
from wendougee_data.control_session import Command, ControlRejected, ControlSession

from .test_control_session import Machine, run_async


class CleaningMachine(Machine):
    def __init__(self):
        super().__init__()
        self.words[:3] = [50, 50, 3]
        self.words[7] = 0

    async def send(self, request):
        if request[1] == 5:
            self.sent.append(request)
            if request[4] == 255 and self.drop_press:
                return
            if request[4] == 0:
                self.bits = 0x20
            self.on_data(request)
        else:
            await super().send(request)


@run_async
@pytest.mark.parametrize("program", [[50, 50, 3], [100, 20, 2]])
async def test_cleaning_reads_program_without_changing_it(program):
    machine = CleaningMachine()
    machine.words[:3] = program
    before = tuple(machine.words)
    async with ControlSession(machine) as session:
        configuration, state = await start_cleaning(session)
    assert state.state == "cleaning"
    assert configuration.raw_registers == before == tuple(machine.words)
    assert [r.hex() for r in machine.sent if r[1] == 5] == [
        "0105009bff00fdd5",
        "0105009b0000bc25",
    ]
    assert all(r[1] in (1, 3, 5) for r in machine.sent)


@run_async
@pytest.mark.parametrize(
    "failure", ["busy", "unknown", "alarm", "cold", "zero", "too_long"]
)
async def test_invalid_preconditions_never_pulse(failure):
    machine = CleaningMachine()
    machine.bits = {"busy": 0x20, "unknown": 0x4000}.get(failure, 0)
    machine.alarm = failure == "alarm"
    if failure == "cold":
        machine.words[7] = 1
    if failure == "zero":
        machine.words[0] = 0
    if failure == "too_long":
        machine.words[:3] = [600, 600, 10]
    async with ControlSession(machine) as session:
        with pytest.raises(ControlRejected):
            await start_cleaning(session)
    assert all(r[1] in (1, 3) for r in machine.sent)


@run_async
async def test_missing_press_echo_still_releases_once():
    machine = CleaningMachine()
    machine.drop_press = True
    async with ControlSession(machine, timeout=0.01) as session:
        with pytest.raises(TimeoutError):
            await start_cleaning(session)
    assert len([r for r in machine.sent if r[1] == 5]) == 2


@run_async
async def test_cancelled_press_releases_before_disconnect():
    machine = CleaningMachine()
    async with ControlSession(machine) as session:
        task = asyncio.create_task(start_cleaning(session))
        while not any(r[1] == 5 for r in machine.sent):
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert machine.sent[-1][4:6] == b"\x00\x00"


@run_async
async def test_configuration_change_after_pulse_is_uncertain():
    class Changed(CleaningMachine):
        async def send(self, request):
            await super().send(request)
            if request[1] == 5 and request[4] == 0:
                self.words[0] += 10

    async with ControlSession(Changed()) as session:
        with pytest.raises(ValueError, match="configuration"):
            await start_cleaning(session)


def test_cleaning_adds_only_exact_coil_155_commands():
    assert Command.CLEANING_PRESS.value == (5, 155, 0xFF00)
    assert Command.CLEANING_RELEASE.value == (5, 155, 0)
