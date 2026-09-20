"""Constrained live read support for supervised DATA S validation."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Any

from .const import (
    ADVERTISEMENT_PREFIX,
    EVENT_CHARACTERISTIC_UUID,
    MODBUS_CHARACTERISTIC_UUID,
    SERVICE_UUID,
)
from .modbus import build_read_holding_registers_request
from .telemetry import Telemetry, TelemetryResponseAssembler


class LiveReadError(RuntimeError):
    """Raised when a live read cannot be completed safely."""


async def _discover_data_machine(timeout: float) -> Any:
    from bleak import BleakScanner

    device = await BleakScanner.find_device_by_filter(
        lambda candidate, advertisement: (
            advertisement.local_name or candidate.name or ""
        ).startswith(ADVERTISEMENT_PREFIX),
        timeout=timeout,
    )
    if device is None:
        raise LiveReadError("no WDG_Data_* advertisement found")
    return device


def _require_gatt_layout(client: Any) -> tuple[Any, Any]:
    service = client.services.get_service(SERVICE_UUID)
    if service is None:
        raise LiveReadError("expected Wendougee service was not found")

    modbus = client.services.get_characteristic(MODBUS_CHARACTERISTIC_UUID)
    event = client.services.get_characteristic(EVENT_CHARACTERISTIC_UUID)
    if modbus is None or event is None:
        raise LiveReadError("expected Wendougee characteristics were not found")

    modbus_properties = set(modbus.properties)
    if "notify" not in modbus_properties:
        raise LiveReadError("Modbus characteristic does not support notifications")
    if not {"write-without-response", "write"} & modbus_properties:
        raise LiveReadError("Modbus characteristic does not support a known write mode")
    if "notify" not in set(event.properties):
        raise LiveReadError("event characteristic does not support notifications")
    return modbus, event


async def inspect_live_machine(scan_timeout: float = 15.0) -> None:
    """Connect and verify the expected service layout without sending a write."""
    from bleak import BleakClient

    device = await _discover_data_machine(scan_timeout)
    async with BleakClient(device, timeout=15.0) as client:
        _require_gatt_layout(client)


async def read_live_telemetry(
    scan_timeout: float = 15.0,
    response_timeout: float = 8.0,
) -> Telemetry:
    """Send only the documented function-03 read and return validated telemetry."""
    from bleak import BleakClient

    device = await _discover_data_machine(scan_timeout)
    async with BleakClient(device, timeout=15.0) as client:
        modbus_characteristic, event_characteristic = _require_gatt_layout(client)

        loop = asyncio.get_running_loop()
        result: asyncio.Future[Telemetry] = loop.create_future()
        assembler = TelemetryResponseAssembler()

        def on_modbus_notification(_sender: Any, data: bytearray) -> None:
            if result.done():
                return
            try:
                telemetry = assembler.feed(bytes(data))
            except ValueError as error:
                result.set_exception(error)
                return
            if telemetry is not None:
                result.set_result(telemetry)

        def on_event_notification(_sender: Any, _data: bytearray) -> None:
            return

        await client.start_notify(modbus_characteristic, on_modbus_notification)
        await client.start_notify(event_characteristic, on_event_notification)
        try:
            request = build_read_holding_registers_request(
                start_address=1404,
                count=22,
            )
            await client.write_gatt_char(
                modbus_characteristic,
                request,
                response=(
                    "write-without-response" not in modbus_characteristic.properties
                ),
            )
            return await asyncio.wait_for(result, timeout=response_timeout)
        finally:
            if client.is_connected:
                await client.stop_notify(event_characteristic)
                await client.stop_notify(modbus_characteristic)


def main() -> None:
    """Run a redacted supervised inspection or telemetry read."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--read-telemetry",
        action="store_true",
        help="send the single documented function-03 telemetry request",
    )
    arguments = parser.parse_args()

    if not arguments.read_telemetry:
        asyncio.run(inspect_live_machine())
        print("Expected WDG_Data_* advertisement and GATT layout verified.")
        return

    telemetry = asyncio.run(read_live_telemetry())
    print(json.dumps(asdict(telemetry), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
