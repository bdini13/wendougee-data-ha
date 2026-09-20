"""Offline safety checks for the constrained live client."""

from __future__ import annotations

import unittest

from wendougee_data.const import (
    EVENT_CHARACTERISTIC_UUID,
    MODBUS_CHARACTERISTIC_UUID,
    SERVICE_UUID,
)
from wendougee_data.live import LiveReadError, _require_gatt_layout


class _Characteristic:
    def __init__(self, properties: set[str]) -> None:
        self.properties = properties


class _Services:
    def __init__(self, modbus_properties: set[str]) -> None:
        self._service = object()
        self._characteristics = {
            MODBUS_CHARACTERISTIC_UUID: _Characteristic(modbus_properties),
            EVENT_CHARACTERISTIC_UUID: _Characteristic({"notify"}),
        }

    def get_service(self, uuid: str) -> object | None:
        return self._service if uuid == SERVICE_UUID else None

    def get_characteristic(self, uuid: str) -> _Characteristic | None:
        return self._characteristics.get(uuid)


class _Client:
    def __init__(self, modbus_properties: set[str]) -> None:
        self.services = _Services(modbus_properties)


class GattLayoutTests(unittest.TestCase):
    def test_accepts_expected_read_transport_properties(self) -> None:
        _require_gatt_layout(_Client({"notify", "write-without-response"}))

    def test_rejects_characteristic_without_write_support(self) -> None:
        with self.assertRaisesRegex(LiveReadError, "write mode"):
            _require_gatt_layout(_Client({"notify"}))


if __name__ == "__main__":
    unittest.main()
