"""Allowlisted read requests and strict RTU framing, independent of Bluetooth.

Protocol facts and provenance: CAPABILITIES.md and docs/VALIDATION_PLAN.md.
Corrupt streams fail closed; callers must establish a fresh connection/session.
"""

from enum import Enum

from .crc import append_crc, crc16_modbus


class ReadOperation(Enum):
    """The only device operations accepted by the read session."""

    TELEMETRY = (3, 1404, 22)
    CONFIGURATION = (3, 0, 37)
    WATER_ALARM_ENABLED = (3, 396, 1)
    OPERATING_STATE = (1, 182, 24)

    @property
    def function(self) -> int:
        """Return the fixed Modbus function for this allowlisted operation."""
        return self.value[0]

    @property
    def byte_count(self) -> int:
        """Registers use two bytes each; coils are packed eight bits per byte."""
        count = self.value[2]
        return count * 2 if self.function == 3 else (count + 7) // 8


class DeviceException(ValueError):
    """CRC-valid Modbus exception, with its numeric device exception code."""

    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"device returned Modbus exception {code}")


def _require_operation(operation: ReadOperation) -> None:
    if not isinstance(operation, ReadOperation):
        raise ValueError("operation must be an allowlisted ReadOperation")


def build_read_request(operation: ReadOperation) -> bytes:
    """Build one fixed, read-only operation; no arbitrary addresses or writes."""
    _require_operation(operation)
    function, address, count = operation.value
    return append_crc(
        bytes((1, function)) + address.to_bytes(2, "big") + count.to_bytes(2, "big")
    )


def _validate_crc(frame: bytes) -> None:
    if crc16_modbus(frame[:-2]) != int.from_bytes(frame[-2:], "little"):
        raise ValueError("response CRC mismatch")


def validate_read_response(frame: bytes, operation: ReadOperation) -> bytes:
    """Validate identity, shape and CRC; return only the expected payload.

    FC03 replies do not echo the requested address. A serialized session and a
    fresh connection after uncertainty are required, but cannot authenticate
    an unsolicited same-shaped reply from the device.
    """
    _require_operation(operation)
    if len(frame) < 5:
        raise ValueError("response is too short")
    if frame[0] != 1:
        raise ValueError("unexpected slave address")
    if frame[1] == operation.function | 0x80:
        if len(frame) != 5:
            raise ValueError("invalid exception response length")
        _validate_crc(frame)
        raise DeviceException(frame[2])
    if frame[1] != operation.function:
        raise ValueError("unexpected function")
    if frame[2] != operation.byte_count:
        raise ValueError("unexpected response byte count")
    if len(frame) != operation.byte_count + 5:
        raise ValueError("unexpected response length")
    _validate_crc(frame)
    return frame[3:-2]


class ReadResponseStream:
    """Bounded fragment/coalescing support for FC01/FC03 and their exceptions.

    No speculative byte-skipping after corruption: misalignment can otherwise
    turn stale or unrelated bytes into apparently valid current measurements.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._failed = False

    @property
    def pending_bytes(self) -> int:
        """Expose leftover bytes so a session can reject unsolicited trailers."""
        return len(self._buffer)

    def feed(self, fragment: bytes) -> list[bytes]:
        """Extract complete frames or permanently fail this stream on corruption."""
        if self._failed:
            raise ValueError("response stream has failed")
        try:
            return self._extract(fragment)
        except ValueError:
            self._failed = True
            self._buffer.clear()
            raise

    def _extract(self, fragment: bytes) -> list[bytes]:
        if len(self._buffer) + len(fragment) > 512:
            raise ValueError("response buffer limit exceeded")
        self._buffer.extend(fragment)
        frames = []
        while self._buffer:
            if self._buffer[0] != 1:
                raise ValueError("unexpected slave address in stream")
            if len(self._buffer) < 2:
                break
            function = self._buffer[1]
            if function not in (1, 3, 0x81, 0x83):
                raise ValueError("unexpected function in stream")
            if len(self._buffer) < 3:
                break
            if function & 0x80:
                length = 5
            else:
                count = self._buffer[2]
                if not 1 <= count <= 250 or (function == 3 and count % 2):
                    raise ValueError("invalid response byte count")
                length = count + 5
            if len(self._buffer) < length:
                break
            frame = bytes(self._buffer[:length])
            _validate_crc(frame)
            frames.append(frame)
            del self._buffer[:length]
        return frames
