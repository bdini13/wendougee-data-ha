"""Offline safety checks for the constrained live client."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from wendougee_data.const import (
    EVENT_CHARACTERISTIC_UUID,
    MODBUS_CHARACTERISTIC_UUID,
    SERVICE_UUID,
)
from wendougee_data.live import (
    LiveReadError,
    _BleakReadTransport,
    _require_gatt_layout,
    read_live_telemetry,
)
from wendougee_data.reads import ReadOperation
from wendougee_data.session import ReadSession, SessionUnavailable

from .test_telemetry import TELEMETRY_RESPONSE


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


class FakeBleakClient(_Client):
    def __init__(self):
        super().__init__({"notify", "write-without-response"})
        self.is_connected = False
        self.disconnect_called = False
        self.notifications = {}
        self.stopped = []
        self.sent = []
        self.fail_event_subscription = False
        self.fail_stop = False
        self.trigger_disconnect = False
        self.write_responses = []

    async def connect(self):
        self.is_connected = True

    async def start_notify(self, characteristic, callback):
        event = self.services.get_characteristic(EVENT_CHARACTERISTIC_UUID)
        if characteristic is event and self.fail_event_subscription:
            raise RuntimeError("subscription failed")
        self.notifications[characteristic] = callback

    async def stop_notify(self, characteristic):
        self.stopped.append(characteristic)
        if self.fail_stop:
            raise RuntimeError("unsubscribe failed")

    async def write_gatt_char(self, characteristic, request, *, response):
        self.sent.append(request)
        self.write_responses.append(response)
        assert len(self.notifications) == 2
        if self.trigger_disconnect:
            self.is_connected = False
            self.disconnected_callback(self)
        else:
            self.notifications[characteristic](characteristic, TELEMETRY_RESPONSE)

    async def disconnect(self):
        self.disconnect_called = True
        self.is_connected = False


class BleakTransportTests(unittest.IsolatedAsyncioTestCase):
    def client_factory(self, _device, *, disconnected_callback, **_kwargs):
        self.client.disconnected_callback = disconnected_callback
        return self.client

    async def asyncSetUp(self):
        self.client = FakeBleakClient()
        self.patch = patch("bleak.BleakClient", self.client_factory)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_notifications_ready_before_single_allowlisted_read(self):
        async with ReadSession(_BleakReadTransport(object())) as session:
            frame = await session.read(ReadOperation.TELEMETRY)
            self.assertEqual(frame, TELEMETRY_RESPONSE)
        self.assertEqual(self.client.sent, [bytes.fromhex("0103057c00160510")])
        self.assertTrue(self.client.disconnect_called)
        self.assertEqual(len(self.client.stopped), 2)

    async def test_partial_subscription_failure_still_disconnects_without_sending(self):
        self.client.fail_event_subscription = True
        with self.assertRaisesRegex(RuntimeError, "subscription failed"):
            async with ReadSession(_BleakReadTransport(object())):
                self.fail("must not enter")
        self.assertTrue(self.client.disconnect_called)
        self.assertEqual(self.client.sent, [])
        self.assertEqual(len(self.client.stopped), 2)

    async def test_cleanup_attempts_all_subscriptions_and_disconnect_on_error(self):
        self.client.fail_stop = True
        with self.assertRaisesRegex(LiveReadError, "cleanup"):
            async with ReadSession(_BleakReadTransport(object())):
                pass
        self.assertTrue(self.client.disconnect_called)
        self.assertEqual(len(self.client.stopped), 2)

    async def test_disconnect_callback_reaches_session(self):
        self.client.trigger_disconnect = True
        with self.assertRaises(SessionUnavailable):
            async with ReadSession(_BleakReadTransport(object())) as session:
                await session.read(ReadOperation.TELEMETRY)
        self.assertTrue(self.client.disconnect_called)

    async def test_adapter_itself_rejects_arbitrary_command_bytes(self):
        transport = _BleakReadTransport(object())
        async with ReadSession(transport):
            with self.assertRaisesRegex(ValueError, "allowlisted"):
                await transport.send(bytes.fromhex("01050096ff006c16"))
        self.assertEqual(self.client.sent, [])

    async def test_public_client_only_sends_telemetry_with_fake_discovery(self):
        with patch(
            "wendougee_data.live._discover_data_machine", new_callable=AsyncMock
        ):
            telemetry = await read_live_telemetry()
        self.assertEqual(telemetry.brew_boiler_temperature_celsius, 93.6)
        self.assertEqual(self.client.sent, [bytes.fromhex("0103057c00160510")])
        self.assertEqual(self.client.write_responses, [False])

    async def test_write_with_response_fallback(self):
        characteristic = self.client.services.get_characteristic(
            MODBUS_CHARACTERISTIC_UUID
        )
        characteristic.properties = {"notify", "write"}
        async with ReadSession(_BleakReadTransport(object())) as session:
            await session.read(ReadOperation.TELEMETRY)
        self.assertEqual(self.client.write_responses, [True])


if __name__ == "__main__":
    unittest.main()
