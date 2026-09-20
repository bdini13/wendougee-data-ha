"""CRC16-Modbus fixtures from the documented safe telemetry request."""

import unittest

from wendougee_data.crc import append_crc, crc16_modbus


class Crc16ModbusTests(unittest.TestCase):
    def test_known_telemetry_request_crc(self) -> None:
        payload = bytes.fromhex("01 03 05 7c 00 16")

        self.assertEqual(crc16_modbus(payload), 0x1005)

    def test_append_crc_uses_low_byte_first_wire_order(self) -> None:
        payload = bytes.fromhex("01 03 05 7c 00 16")

        self.assertEqual(
            append_crc(payload),
            bytes.fromhex("01 03 05 7c 00 16 05 10"),
        )


if __name__ == "__main__":
    unittest.main()
