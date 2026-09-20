"""Constrained live read support for supervised DATA S validation."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from .const import (
    ADVERTISEMENT_PREFIX,
    EVENT_CHARACTERISTIC_UUID,
    MODBUS_CHARACTERISTIC_UUID,
    SERVICE_UUID,
)
from .reads import ReadOperation, build_read_request
from .session import ReadSession
from .telemetry import Telemetry, parse_telemetry_response


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


class _BleakReadTransport:
    """Standalone adapter; HA must supply its own shared-Bluetooth transport.

    Construction performs no I/O. Even this low-level adapter rejects command
    bytes outside the four fixed read operations. No FF55 messages are sent.
    """

    def __init__(self, device: Any) -> None:
        self._device = device
        self._client: Any = None
        self._modbus: Any = None
        self._subscriptions: list[Any] = []

    async def open(
        self, on_data: Callable[[bytes], None], on_disconnect: Callable[[], None]
    ) -> None:
        """Connect the chosen device and await both notification subscriptions."""
        from bleak import BleakClient

        self._client = BleakClient(
            self._device,
            timeout=15.0,
            disconnected_callback=lambda _client: on_disconnect(),
        )
        await self._client.connect()
        self._modbus, event = _require_gatt_layout(self._client)
        # Track attempted subscriptions too, so partial setup is cleaned up.
        self._subscriptions.append(self._modbus)
        await self._client.start_notify(
            self._modbus, lambda _sender, data: on_data(bytes(data))
        )
        self._subscriptions.append(event)
        await self._client.start_notify(event, lambda _sender, _data: None)

    async def send(self, request: bytes) -> None:
        """Enforce the read allowlist again at the last boundary before Bluetooth."""
        if request not in {
            build_read_request(operation) for operation in ReadOperation
        }:
            raise ValueError("request must be an allowlisted read")
        if self._client is None or self._modbus is None:
            raise LiveReadError("transport not ready")
        await self._client.write_gatt_char(
            self._modbus,
            request,
            response=("write-without-response" not in self._modbus.properties),
        )

    async def close(self) -> None:
        """Attempt every cleanup step without letting unsubscribe block disconnect."""
        if self._client is None:
            return
        cleanup_failed = False
        try:
            for characteristic in reversed(self._subscriptions):
                if not self._client.is_connected:
                    break
                try:
                    async with asyncio.timeout(2.0):
                        await self._client.stop_notify(characteristic)
                except Exception:
                    cleanup_failed = True
        finally:
            self._subscriptions.clear()
            # Also runs after cancellation or a partial connection failure.
            async with asyncio.timeout(2.0):
                await self._client.disconnect()
        if cleanup_failed:
            raise LiveReadError("notification cleanup failed; disconnect attempted")


async def read_live_telemetry(
    scan_timeout: float = 15.0,
    response_timeout: float = 8.0,
) -> Telemetry:
    """Send only the documented function-03 read and return validated telemetry."""
    device = await _discover_data_machine(scan_timeout)
    async with ReadSession(
        _BleakReadTransport(device), timeout=response_timeout
    ) as session:
        frame = await session.read(ReadOperation.TELEMETRY)
        return parse_telemetry_response(frame)


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
