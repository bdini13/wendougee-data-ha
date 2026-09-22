"""Offline-only boiler setting frames; no transport or Home Assistant controls.

These four operations are documented by pinned upstream sources but remain
unvalidated on the local DATA S. Building a frame is not permission to send it.
Any future live transaction must use an attended, separately approved workflow,
correlate the exact echo, reconnect after uncertainty, and verify the complete
configuration block before reporting success.
"""

from enum import Enum

from .crc import append_crc, crc16_modbus
from .reads import DeviceException

WRITE_SINGLE_REGISTER = 0x06


class BoilerSetting(Enum):
    """The complete boiler-setting allowlist known from upstream evidence."""

    STEAM_ENABLED = (6, 0, 1)
    BREW_ENABLED = (7, 0, 1)
    STEAM_TARGET_CELSIUS = (8, 0, 140)
    BREW_TARGET_CELSIUS = (9, 0, 110)

    @property
    def register(self) -> int:
        """Return the documented holding-register address."""
        return self.value[0]


def build_boiler_setting_request(setting: BoilerSetting, value: bool | int) -> bytes:
    """Build one bounded FC06 request without accepting an arbitrary address.

    The broad temperature limits are upstream application limits, not locally
    validated safe setpoints. Future UI limits must be narrower and separately
    justified before a transport can send these frames.
    """
    if not isinstance(setting, BoilerSetting):
        raise ValueError("setting must be an allowlisted BoilerSetting")

    if setting in {BoilerSetting.STEAM_ENABLED, BoilerSetting.BREW_ENABLED}:
        if type(value) is not bool:
            raise ValueError("boiler enabled value must be a boolean")
        encoded = 0 if value else 1
    else:
        if type(value) is not int:
            raise ValueError("temperature must be a whole number")
        minimum, maximum = setting.value[1:]
        if not minimum <= value <= maximum:
            raise ValueError(f"temperature must be between {minimum} and {maximum} °C")
        encoded = value

    payload = bytes((1, WRITE_SINGLE_REGISTER))
    payload += setting.register.to_bytes(2, "big")
    payload += encoded.to_bytes(2, "big")
    return append_crc(payload)


def validate_write_echo(response: bytes, request: bytes) -> None:
    """Require a CRC-valid exact FC06 echo or raise a numeric device exception."""
    if len(response) < 5:
        raise ValueError("write response is too short")
    if response[0] != 1:
        raise ValueError("unexpected slave address")
    if crc16_modbus(response[:-2]) != int.from_bytes(response[-2:], "little"):
        raise ValueError("write response CRC mismatch")
    if response[1] == WRITE_SINGLE_REGISTER | 0x80:
        if len(response) != 5:
            raise ValueError("invalid write exception response length")
        raise DeviceException(response[2])
    if response[1] != WRITE_SINGLE_REGISTER or len(response) != 8:
        raise ValueError("unexpected write response shape")
    if response != request:
        raise ValueError("write response does not match the request")


__all__ = [
    "BoilerSetting",
    "DeviceException",
    "build_boiler_setting_request",
    "validate_write_echo",
]
