"""Provisional DATA S configuration/status decoding, without control paths.

Derived from protocol facts in CAPABILITIES.md, not hardware-calibrated here.
Unknown enum values stay unknown; raw values are retained for private analysis.
"""

from dataclasses import dataclass

from .reads import ReadOperation, validate_read_response


@dataclass(frozen=True)
class Configuration:
    """Decoded settings; unknown booleans/modes stay None, not guessed defaults."""

    cleaning_time_seconds: float
    cleaning_rest_seconds: float
    cleaning_repetitions: int
    steam_heating_enabled: bool | None
    brew_heating_enabled: bool | None
    steam_target_celsius: int
    brew_target_celsius: int
    manual_time_seconds: float
    manual_pressure_bar: float
    heating_mode: str | None
    raw_registers: tuple[int, ...]


def decode_configuration(frame: bytes) -> Configuration:
    """Validate the 37-word block and apply only documented field conversions."""
    payload = validate_read_response(frame, ReadOperation.CONFIGURATION)
    words = tuple(
        int.from_bytes(payload[index : index + 2], "big")
        for index in range(0, len(payload), 2)
    )
    return Configuration(
        cleaning_time_seconds=words[0] / 10,
        cleaning_rest_seconds=words[1] / 10,
        cleaning_repetitions=words[2],
        steam_heating_enabled={0: True, 1: False}.get(words[6]),
        brew_heating_enabled={0: True, 1: False}.get(words[7]),
        steam_target_celsius=words[8],
        brew_target_celsius=words[9],
        manual_time_seconds=words[17] / 10,
        manual_pressure_bar=words[19] / 10,
        heating_mode={0: "pulse", 1: "full_speed"}.get(words[22]),
        raw_registers=words,
    )


def decode_water_alarm_enabled(frame: bytes) -> bool | None:
    """Read alarm configuration, not whether a water shortage is currently active."""
    payload = validate_read_response(frame, ReadOperation.WATER_ALARM_ENABLED)
    return {0: False, 1: True}.get(int.from_bytes(payload, "big"))


@dataclass(frozen=True)
class OperatingState:
    """Retain all flags so contradictory/unknown states remain diagnosable."""

    raw_bits: int
    profile_active: bool
    manual_active: bool
    cleaning_active: bool
    free_variable_active: bool
    unknown_bits: int

    @property
    def state(self) -> str:
        """Do not use a priority rule to hide simultaneous operating modes."""
        active = [
            name
            for name, enabled in (
                ("profile", self.profile_active),
                ("manual", self.manual_active),
                ("cleaning", self.cleaning_active),
                ("free_variable", self.free_variable_active),
            )
            if enabled
        ]
        if len(active) > 1:
            return "ambiguous"
        if self.unknown_bits:
            return "unknown"
        return active[0] if active else "idle"


def decode_operating_state(frame: bytes) -> OperatingState:
    """Decode the 24-coil response using provisional upstream DATA S masks."""
    payload = validate_read_response(frame, ReadOperation.OPERATING_STATE)
    bits = int.from_bytes(payload, "little")
    return OperatingState(
        raw_bits=bits,
        profile_active=bool(bits & 0x03),
        manual_active=bool(bits & 0x10),
        cleaning_active=bool(bits & 0x20),
        free_variable_active=bool(bits & 0x800),
        unknown_bits=bits & ~0x833,
    )
