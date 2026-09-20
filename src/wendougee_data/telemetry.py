"""Decode the documented DATA S read-only telemetry register block."""

from __future__ import annotations

from dataclasses import dataclass

from .crc import crc16_modbus
from .modbus import DEFAULT_SLAVE_ADDRESS, READ_HOLDING_REGISTERS

TELEMETRY_START_REGISTER = 1404
TELEMETRY_REGISTER_COUNT = 22
TELEMETRY_BYTE_COUNT = TELEMETRY_REGISTER_COUNT * 2
TELEMETRY_RESPONSE_LENGTH = TELEMETRY_BYTE_COUNT + 5


@dataclass(frozen=True)
class Telemetry:
    """Typed values decoded from holding registers 1404 through 1425."""

    elapsed_brew_time_seconds: float
    water_level_alarm: bool
    steam_boiler_temperature_celsius: float
    brew_boiler_temperature_celsius: float
    pressure_bar: float
    dispensed_volume_ml: int
    scale_weight_grams: float
    pump_active_time_seconds: int
    instantaneous_flow_ml_per_second: int
    weight_rate_grams_per_second: float


class TelemetryResponseAssembler:
    """Reassemble one fragmented telemetry response without accepting extras."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, fragment: bytes) -> Telemetry | None:
        """Add one notification fragment and return telemetry when complete."""
        self._buffer.extend(fragment)
        if len(self._buffer) > TELEMETRY_RESPONSE_LENGTH:
            raise ValueError("telemetry response is longer than one expected frame")
        if len(self._buffer) < TELEMETRY_RESPONSE_LENGTH:
            return None
        return parse_telemetry_response(bytes(self._buffer))


def parse_telemetry_response(frame: bytes) -> Telemetry:
    """Validate and decode a 22-register function-03 response."""
    if len(frame) != TELEMETRY_RESPONSE_LENGTH:
        raise ValueError(
            f"telemetry response length must be {TELEMETRY_RESPONSE_LENGTH} bytes"
        )
    if frame[0] != DEFAULT_SLAVE_ADDRESS:
        raise ValueError("unexpected Modbus slave address")
    if frame[1] != READ_HOLDING_REGISTERS:
        raise ValueError("unexpected Modbus function")
    if frame[2] != TELEMETRY_BYTE_COUNT:
        raise ValueError(
            f"telemetry byte count must be {TELEMETRY_BYTE_COUNT}, got {frame[2]}"
        )

    expected_crc = int.from_bytes(frame[-2:], byteorder="little")
    actual_crc = crc16_modbus(frame[:-2])
    if actual_crc != expected_crc:
        raise ValueError("telemetry response CRC mismatch")

    payload = frame[3:-2]
    registers = tuple(
        int.from_bytes(payload[offset : offset + 2], byteorder="big")
        for offset in range(0, len(payload), 2)
    )

    return Telemetry(
        elapsed_brew_time_seconds=registers[1405 - TELEMETRY_START_REGISTER] / 10,
        water_level_alarm=bool(registers[1406 - TELEMETRY_START_REGISTER]),
        steam_boiler_temperature_celsius=(
            registers[1408 - TELEMETRY_START_REGISTER] / 10
        ),
        brew_boiler_temperature_celsius=(
            registers[1409 - TELEMETRY_START_REGISTER] / 10
        ),
        pressure_bar=registers[1410 - TELEMETRY_START_REGISTER] / 10,
        dispensed_volume_ml=registers[1411 - TELEMETRY_START_REGISTER],
        scale_weight_grams=registers[1412 - TELEMETRY_START_REGISTER] / 10,
        pump_active_time_seconds=registers[1417 - TELEMETRY_START_REGISTER],
        instantaneous_flow_ml_per_second=(registers[1422 - TELEMETRY_START_REGISTER]),
        weight_rate_grams_per_second=(registers[1423 - TELEMETRY_START_REGISTER] / 10),
    )
