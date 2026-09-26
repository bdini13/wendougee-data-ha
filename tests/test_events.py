import pytest

from wendougee_data.events import (
    DATA_PREFIX,
    OPCODE_PREFIX,
    FF55Variant,
    ff55_checksum,
    parse_ff55_frame,
    parse_heartbeat_event,
)


def _frame(body: bytes) -> bytes:
    return body + bytes((ff55_checksum(body),))


@pytest.mark.parametrize("marker", (0, 1))
def test_decodes_binary_heartbeat_marker_without_inventing_semantics(marker):
    frame = _frame(OPCODE_PREFIX + bytes((0x83, 0, 1, marker)))

    parsed = parse_ff55_frame(frame)

    assert parsed.variant is FF55Variant.OPCODE
    assert parsed.opcode == 0x83
    assert parsed.payload == bytes((marker,))
    assert parse_heartbeat_event(frame).marker == marker


def test_decodes_generic_data_variant_without_field_guesses():
    payload = bytes((0x10, 0x20, 0x30))
    frame = _frame(DATA_PREFIX + bytes((len(payload),)) + payload)

    parsed = parse_ff55_frame(frame)

    assert parsed.variant is FF55Variant.DATA
    assert parsed.opcode is None
    assert parsed.payload == payload


@pytest.mark.parametrize(
    ("frame", "message"),
    (
        (b"\xff\x55", "too short"),
        (_frame(b"\xfe\x55\xff\xff\x83\x00\x01\x00"), "magic"),
        (_frame(OPCODE_PREFIX + b"\x83\x01\x01\x00"), "reserved"),
        (_frame(OPCODE_PREFIX + b"\x83\x00\x02\x00"), "length"),
        (_frame(DATA_PREFIX + b"\x02\x00"), "length"),
        (_frame(b"\xff\x55\x10\x20\x30\x40\x00"), "unknown"),
    ),
)
def test_rejects_malformed_frames(frame, message):
    with pytest.raises(ValueError, match=message):
        parse_ff55_frame(frame)


def test_rejects_bad_checksum():
    frame = bytearray(_frame(OPCODE_PREFIX + b"\x83\x00\x01\x00"))
    frame[-1] ^= 1

    with pytest.raises(ValueError, match="checksum"):
        parse_ff55_frame(bytes(frame))


def test_heartbeat_decoder_rejects_other_or_nonbinary_events():
    for body in (
        OPCODE_PREFIX + b"\x82\x00\x01\x00",
        OPCODE_PREFIX + b"\x83\x00\x01\x02",
        DATA_PREFIX + b"\x01\x00",
    ):
        with pytest.raises(ValueError):
            parse_heartbeat_event(_frame(body))
