"""Offline-only tests for the narrowly allowlisted boiler setting frames."""

import pytest

from wendougee_data.controls import (
    BoilerSetting,
    DeviceException,
    build_boiler_setting_request,
    validate_write_echo,
)
from wendougee_data.crc import append_crc


@pytest.mark.parametrize(
    ("setting", "value", "register", "encoded"),
    [
        (BoilerSetting.STEAM_ENABLED, True, 6, 0),
        (BoilerSetting.STEAM_ENABLED, False, 6, 1),
        (BoilerSetting.BREW_ENABLED, True, 7, 0),
        (BoilerSetting.BREW_ENABLED, False, 7, 1),
        (BoilerSetting.STEAM_TARGET_CELSIUS, 126, 8, 126),
        (BoilerSetting.BREW_TARGET_CELSIUS, 92, 9, 92),
    ],
)
def test_builds_only_documented_single_register_writes(
    setting, value, register, encoded
):
    expected = append_crc(
        b"\x01\x06" + register.to_bytes(2, "big") + encoded.to_bytes(2, "big")
    )
    assert build_boiler_setting_request(setting, value) == expected


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        (BoilerSetting.STEAM_ENABLED, 1),
        (BoilerSetting.BREW_ENABLED, "yes"),
        (BoilerSetting.STEAM_TARGET_CELSIUS, -1),
        (BoilerSetting.STEAM_TARGET_CELSIUS, 141),
        (BoilerSetting.BREW_TARGET_CELSIUS, -1),
        (BoilerSetting.BREW_TARGET_CELSIUS, 111),
        ("register_10", 90),
    ],
)
def test_rejects_wrong_types_ranges_and_arbitrary_registers(setting, value):
    with pytest.raises(ValueError):
        build_boiler_setting_request(setting, value)


def test_write_echo_must_match_the_complete_request():
    request = build_boiler_setting_request(BoilerSetting.BREW_TARGET_CELSIUS, 92)
    assert validate_write_echo(request, request) is None

    wrong_value = build_boiler_setting_request(BoilerSetting.BREW_TARGET_CELSIUS, 93)
    with pytest.raises(ValueError, match="does not match"):
        validate_write_echo(wrong_value, request)

    with pytest.raises(ValueError, match="CRC"):
        validate_write_echo(request[:-1] + b"\x00", request)


def test_write_exception_preserves_only_numeric_code():
    request = build_boiler_setting_request(BoilerSetting.BREW_ENABLED, True)
    response = append_crc(b"\x01\x86\x02")
    with pytest.raises(DeviceException) as captured:
        validate_write_echo(response, request)
    assert captured.value.code == 2
