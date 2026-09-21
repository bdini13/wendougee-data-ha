"""Short read-only connections through Home Assistant's shared Bluetooth APIs."""

import asyncio
from collections.abc import Callable

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ._protocol.const import (
    EVENT_CHARACTERISTIC_UUID,
    MODBUS_CHARACTERISTIC_UUID,
    SERVICE_UUID,
)
from ._protocol.reads import ReadOperation, build_read_request
from ._protocol.session import ReadSession
from ._protocol.telemetry import Telemetry, parse_telemetry_response


class HomeAssistantReadTransport:
    """No scanner, FF55 initialization, pairing, or control commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        *,
        allowed_operations: frozenset[ReadOperation] = frozenset(
            {ReadOperation.TELEMETRY}
        ),
    ) -> None:
        self.hass = hass
        self.address = address
        self.allowed_operations = allowed_operations
        self.client = None
        self.modbus = None
        self.subscriptions = []

    async def open(
        self, on_data: Callable[[bytes], None], on_disconnect: Callable[[], None]
    ) -> None:
        """Resolve HA's current connectable route and await GATT readiness."""
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise ConnectionError("No connectable Bluetooth path")
        self.client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            "Wendougee DATA",
            disconnected_callback=lambda _client: on_disconnect(),
            max_attempts=1,
        )
        services = self.client.services
        service = services.get_service(SERVICE_UUID)
        self.modbus = services.get_characteristic(MODBUS_CHARACTERISTIC_UUID)
        event = services.get_characteristic(EVENT_CHARACTERISTIC_UUID)
        if service is None or self.modbus is None or event is None:
            raise ValueError("Expected GATT layout missing")
        if "notify" not in self.modbus.properties or "notify" not in event.properties:
            raise ValueError("Expected notification properties missing")
        if not {"write", "write-without-response"} & set(self.modbus.properties):
            raise ValueError("Expected read-request transport missing")
        self.subscriptions.append(self.modbus)
        await self.client.start_notify(
            self.modbus, lambda _sender, data: on_data(bytes(data))
        )
        self.subscriptions.append(event)
        await self.client.start_notify(event, lambda _sender, _data: None)

    async def send(self, request: bytes) -> None:
        """Enforce the caller's fixed read allowlist at the Bluetooth boundary."""
        if request not in {
            build_read_request(operation) for operation in self.allowed_operations
        }:
            raise ValueError("Request is not enabled for this read-only session")
        if self.client is None or self.modbus is None:
            raise ConnectionError("Transport not ready")
        await self.client.write_gatt_char(
            self.modbus,
            request,
            response="write-without-response" not in self.modbus.properties,
        )

    async def close(self) -> None:
        """Bound unsubscribe/disconnect attempts, including partial setup failure."""
        if self.client is None:
            return
        failed = False
        try:
            for characteristic in reversed(self.subscriptions):
                if not self.client.is_connected:
                    break
                try:
                    async with asyncio.timeout(2):
                        await self.client.stop_notify(characteristic)
                except Exception:
                    failed = True
        finally:
            self.subscriptions.clear()
            async with asyncio.timeout(2):
                await self.client.disconnect()
        if failed:
            raise ConnectionError("Notification cleanup failed")


async def read_telemetry(hass: HomeAssistant, address: str) -> Telemetry:
    """Release the single-central connection after every sample or error."""
    async with ReadSession(
        HomeAssistantReadTransport(hass, address), timeout=15
    ) as session:
        frame = await session.read(ReadOperation.TELEMETRY)
        return parse_telemetry_response(frame)


async def read_baseline(
    hass: HomeAssistant, address: str
) -> dict[ReadOperation, bytes]:
    """Read each fixed baseline operation once with no retry or decoding."""
    frames: dict[ReadOperation, bytes] = {}
    transport = HomeAssistantReadTransport(
        hass,
        address,
        allowed_operations=frozenset(ReadOperation),
    )
    async with ReadSession(transport, timeout=15) as session:
        for operation in ReadOperation:
            frames[operation] = await session.read(operation)
    return frames
