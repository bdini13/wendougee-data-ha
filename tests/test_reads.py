"""Synthetic fixtures for allowlisted reads; none are hardware captures."""

import pytest

from wendougee_data.crc import append_crc
from wendougee_data.reads import (
    DeviceException,
    ReadOperation,
    ReadResponseStream,
    build_read_request,
    validate_read_response,
)
from wendougee_data.state import (
    decode_configuration,
    decode_operating_state,
    decode_water_alarm_enabled,
)


def register_response(values: list[int]) -> bytes:
    payload = b"".join(value.to_bytes(2, "big") for value in values)
    return append_crc(bytes((1, 3, len(payload))) + payload)


@pytest.mark.parametrize(
    ("operation", "frame"),
    [
        (ReadOperation.TELEMETRY, "0103057c00160510"),
        (ReadOperation.CONFIGURATION, "0103000000258411"),
        (ReadOperation.OPERATING_STATE, "010100b60018dde6"),
    ],
)
def test_known_requests(operation, frame):
    assert build_read_request(operation) == bytes.fromhex(frame)


def test_alarm_read_is_separate_and_only_allowlisted_operations_are_accepted():
    assert build_read_request(ReadOperation.WATER_ALARM_ENABLED) == append_crc(
        bytes.fromhex("0103018c0001")
    )
    for invalid in [(3, 0, 37), b"\x01\x05", "TELEMETRY", None]:
        with pytest.raises(ValueError, match="allowlisted"):
            build_read_request(invalid)


def test_configuration_units_and_inverted_polarity():
    values = [0] * 37
    for address, value in {
        0: 55,
        1: 125,
        2: 4,
        6: 1,
        7: 0,
        8: 125,
        9: 94,
        17: 315,
        19: 85,
        22: 1,
        36: 456,
    }.items():
        values[address] = value
    config = decode_configuration(register_response(values))
    assert config.cleaning_time_seconds == 5.5
    assert config.cleaning_rest_seconds == 12.5
    assert config.cleaning_repetitions == 4
    assert config.steam_heating_enabled is False
    assert config.brew_heating_enabled is True
    assert config.steam_target_celsius == 125
    assert config.brew_target_celsius == 94
    assert config.manual_time_seconds == 31.5
    assert config.manual_pressure_bar == 8.5
    assert config.heating_mode == "full_speed"
    assert config.raw_registers == tuple(values)


def test_unknown_configuration_enum_values_are_not_silently_false():
    values = [0] * 37
    values[6], values[7], values[22] = 2, 65535, 8
    config = decode_configuration(register_response(values))
    assert config.steam_heating_enabled is None
    assert config.brew_heating_enabled is None
    assert config.heating_mode is None
    values[6], values[7], values[22] = 0, 1, 0
    config = decode_configuration(register_response(values))
    assert config.steam_heating_enabled is True
    assert config.brew_heating_enabled is False
    assert config.heating_mode == "pulse"


@pytest.mark.parametrize(("value", "expected"), [(0, False), (1, True), (2, None)])
def test_water_alarm_enable_is_not_alarm_assertion(value, expected):
    assert decode_water_alarm_enabled(register_response([value])) is expected


@pytest.mark.parametrize(
    ("bits", "expected"),
    [
        (0, "idle"),
        (1, "profile"),
        (2, "profile"),
        (3, "profile"),
        (16, "manual"),
        (32, "cleaning"),
        (2048, "free_variable"),
        (16 | 32, "ambiguous"),
        (16 | 2048, "ambiguous"),
        (1 << 23, "unknown"),
        (16 | 64, "unknown"),
    ],
)
def test_state_preserves_conflicting_and_unknown_bits(bits, expected):
    frame = append_crc(b"\x01\x01\x03" + bits.to_bytes(3, "little"))
    state = decode_operating_state(frame)
    assert state.state == expected
    assert state.raw_bits == bits
    assert state.unknown_bits == bits & ~0x833
    assert state.manual_active == bool(bits & 16)
    assert state.cleaning_active == bool(bits & 32)


@pytest.mark.parametrize("operation", list(ReadOperation))
def test_validates_normal_and_exception_responses(operation):
    size = operation.byte_count
    frame = append_crc(bytes((1, operation.function, size)) + bytes(size))
    assert validate_read_response(frame, operation) == bytes(size)
    error = append_crc(bytes((1, operation.function | 0x80, 2)))
    with pytest.raises(DeviceException) as caught:
        validate_read_response(error, operation)
    assert caught.value.code == 2


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        append_crc(b"\x02\x03\x02\x00\x01"),
        append_crc(b"\x01\x01\x02\x00\x01"),
        append_crc(b"\x01\x03\x04\x00\x01\x00\x01"),
        append_crc(b"\x01\x83\x02\x00"),
        b"\x01\x03\x02\x00\x01\x00\x00",
    ],
)
def test_rejects_wrong_slave_function_count_length_or_crc(frame):
    with pytest.raises(ValueError):
        validate_read_response(frame, ReadOperation.WATER_ALARM_ENABLED)


def test_stream_handles_every_fragment_boundary_and_coalescing():
    first = register_response([1])
    second = append_crc(b"\x01\x81\x02")
    for boundary in range(1, len(first)):
        stream = ReadResponseStream()
        assert stream.feed(first[:boundary]) == []
        assert stream.feed(first[boundary:] + second) == [first, second]
        assert stream.pending_bytes == 0


@pytest.mark.parametrize(
    "fragment",
    [
        b"\x02",
        b"\x01\x05",
        b"\x01\x03\xff",
        bytes(600),
        b"\x01\x03\x02\x00\x01\x00\x00",
    ],
)
def test_stream_fails_closed_on_corruption_and_is_bounded(fragment):
    stream = ReadResponseStream()
    with pytest.raises(ValueError):
        stream.feed(fragment)
    with pytest.raises(ValueError, match="failed"):
        stream.feed(register_response([1]))
