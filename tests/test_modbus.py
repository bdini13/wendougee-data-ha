"""Tests for safe, read-only Modbus request construction."""

import unittest

from wendougee_data.modbus import build_read_holding_registers_request


class ReadHoldingRegistersRequestTests(unittest.TestCase):
    def test_builds_documented_safe_telemetry_request(self) -> None:
        self.assertEqual(
            build_read_holding_registers_request(start_address=1404, count=22),
            bytes.fromhex("01 03 05 7c 00 16 05 10"),
        )

    def test_rejects_zero_register_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "count"):
            build_read_holding_registers_request(start_address=1404, count=0)

    def test_rejects_request_past_register_address_space(self) -> None:
        with self.assertRaisesRegex(ValueError, "address"):
            build_read_holding_registers_request(start_address=0xFFFF, count=2)


if __name__ == "__main__":
    unittest.main()
