"""Tests for the DATA S 22-register telemetry response."""

import unittest

from wendougee_data.telemetry import Telemetry, parse_telemetry_response

TELEMETRY_RESPONSE = bytes.fromhex(
    "01 03 2c "
    "00 00 00 7b 00 01 00 00 04 e6 03 a8 00 57 00 2a 00 bb "
    "00 00 00 00 00 00 00 00 00 09 00 00 00 00 00 00 00 00 "
    "00 06 00 17 00 00 00 00 "
    "83 9e"
)


class TelemetryResponseTests(unittest.TestCase):
    def test_decodes_documented_registers(self) -> None:
        telemetry = parse_telemetry_response(TELEMETRY_RESPONSE)

        self.assertEqual(
            telemetry,
            Telemetry(
                elapsed_brew_time_seconds=12.3,
                water_level_alarm=True,
                steam_boiler_temperature_celsius=125.4,
                brew_boiler_temperature_celsius=93.6,
                pressure_bar=8.7,
                dispensed_volume_ml=42,
                scale_weight_grams=18.7,
                pump_active_time_seconds=9,
                instantaneous_flow_ml_per_second=6,
                weight_rate_grams_per_second=2.3,
            ),
        )

    def test_rejects_bad_crc(self) -> None:
        corrupted = TELEMETRY_RESPONSE[:-1] + bytes([TELEMETRY_RESPONSE[-1] ^ 0xFF])

        with self.assertRaisesRegex(ValueError, "CRC"):
            parse_telemetry_response(corrupted)

    def test_rejects_wrong_byte_count(self) -> None:
        response = bytearray(TELEMETRY_RESPONSE)
        response[2] = 42

        with self.assertRaisesRegex(ValueError, "byte count"):
            parse_telemetry_response(bytes(response))


if __name__ == "__main__":
    unittest.main()
