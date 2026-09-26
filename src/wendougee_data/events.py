"""Strict, passive-only decoding for the DATA S FF55 event channel.

This module constructs no frames and exposes no write path. Unknown opcodes and
payloads remain generic data so protocol guesses cannot become commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

FF55_MAGIC = bytes((0xFF, 0x55))
OPCODE_PREFIX = bytes((0xFF, 0x55, 0xFF, 0xFF))
DATA_PREFIX = bytes((0xFF, 0x55, 0x02, 0x59, 0x20, 0x00))
HEARTBEAT_OPCODE = 0x83


class FF55Variant(Enum):
    """Known framing families carried by the event characteristic."""

    OPCODE = "opcode"
    DATA = "data"


@dataclass(frozen=True)
class FF55Frame:
    """One checksum- and length-validated passive event frame."""

    variant: FF55Variant
    payload: bytes
    opcode: int | None = None


@dataclass(frozen=True)
class HeartbeatEvent:
    """Observed opcode-0x83 marker; its binary semantics remain unknown."""

    marker: int


def ff55_checksum(body: bytes) -> int:
    """Return the observed one-byte `(sum(body) + 1) mod 256` checksum."""
    return (sum(body) + 1) & 0xFF


def parse_ff55_frame(frame: bytes) -> FF55Frame:
    """Validate one complete FF55 frame without interpreting unknown payloads."""
    if len(frame) < 8:
        raise ValueError("FF55 frame is too short")
    if not frame.startswith(FF55_MAGIC):
        raise ValueError("FF55 magic mismatch")
    if frame[-1] != ff55_checksum(frame[:-1]):
        raise ValueError("FF55 checksum mismatch")

    if frame.startswith(OPCODE_PREFIX):
        if frame[5] != 0:
            raise ValueError("FF55 opcode reserved byte must be zero")
        payload_length = frame[6]
        if len(frame) != 8 + payload_length:
            raise ValueError("FF55 opcode length mismatch")
        return FF55Frame(
            variant=FF55Variant.OPCODE,
            opcode=frame[4],
            payload=frame[7:-1],
        )

    if frame.startswith(DATA_PREFIX):
        payload_length = frame[6]
        if len(frame) != 8 + payload_length:
            raise ValueError("FF55 data length mismatch")
        return FF55Frame(variant=FF55Variant.DATA, payload=frame[7:-1])

    raise ValueError("unknown FF55 framing variant")


def parse_heartbeat_event(frame: bytes) -> HeartbeatEvent:
    """Decode the locally observed binary marker without assigning semantics."""
    parsed = parse_ff55_frame(frame)
    if (
        parsed.variant is not FF55Variant.OPCODE
        or parsed.opcode != HEARTBEAT_OPCODE
        or len(parsed.payload) != 1
    ):
        raise ValueError("not an FF55 heartbeat event")
    marker = parsed.payload[0]
    if marker not in (0, 1):
        raise ValueError("FF55 heartbeat marker is not binary")
    return HeartbeatEvent(marker=marker)
