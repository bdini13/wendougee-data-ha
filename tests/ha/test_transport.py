"""Exercise the HA Bluetooth adapter without opening a real connection."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.wendougee_data._protocol.reads import (
    ReadOperation,
    build_read_request,
)
from custom_components.wendougee_data._protocol.session import ReadSession
from custom_components.wendougee_data.bluetooth import (
    HomeAssistantReadTransport,
    read_baseline,
    read_runtime,
    read_telemetry,
)
from custom_components.wendougee_data.coordinator import WendougeeCoordinator
from tests.test_live import FakeBleakClient

from .test_integration import ADDRESS, TELEMETRY, entry

pytestmark = pytest.mark.asyncio


@pytest.fixture
def fake_connection():
    client = FakeBleakClient()
    client.is_connected = True
    device = object()

    async def connect(_client_type, supplied_device, _name, **kwargs):
        assert supplied_device is device
        assert kwargs["max_attempts"] == 1
        client.disconnected_callback = kwargs["disconnected_callback"]
        return client

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=device,
        ) as lookup,
        patch(
            "custom_components.wendougee_data.bluetooth.establish_connection",
            side_effect=connect,
        ),
    ):
        yield client, lookup


async def test_shared_device_single_telemetry_read_and_disconnect(
    hass, fake_connection
):
    client, lookup = fake_connection
    telemetry = await read_telemetry(hass, ADDRESS)
    lookup.assert_called_once_with(hass, ADDRESS, connectable=True)
    assert telemetry.pressure_bar == 8.7
    assert client.sent == [build_read_request(ReadOperation.TELEMETRY)]
    assert client.disconnect_called
    assert len(client.stopped) == 2


async def test_missing_connectable_path_does_not_connect(hass):
    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "custom_components.wendougee_data.bluetooth.establish_connection"
        ) as connect,
        pytest.raises(ConnectionError),
    ):
        await read_telemetry(hass, ADDRESS)
    connect.assert_not_called()


async def test_partial_notification_failure_cleans_up(hass, fake_connection):
    client, _ = fake_connection
    client.fail_event_subscription = True
    with pytest.raises(RuntimeError, match="subscription failed"):
        await read_telemetry(hass, ADDRESS)
    assert client.disconnect_called
    assert client.sent == []


async def test_no_other_operations_enabled_in_ha(hass, fake_connection):
    transport = HomeAssistantReadTransport(hass, ADDRESS)
    async with ReadSession(transport):
        for request in [build_read_request(ReadOperation.CONFIGURATION), b"\x01\x05"]:
            with pytest.raises(ValueError, match="not enabled"):
                await transport.send(request)
    assert fake_connection[0].sent == []


async def test_explicit_baseline_reads_each_allowlisted_operation_once(
    hass, fake_connection
):
    from custom_components.wendougee_data._protocol.crc import append_crc
    from tests.test_telemetry import TELEMETRY_RESPONSE

    client, _ = fake_connection
    replies = {
        ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
        ReadOperation.CONFIGURATION: append_crc(b"\x01\x03\x4a" + bytes(74)),
        ReadOperation.WATER_ALARM_ENABLED: append_crc(b"\x01\x03\x02\x00\x01"),
        ReadOperation.OPERATING_STATE: append_crc(b"\x01\x01\x03\x00\x00\x00"),
    }

    async def respond(characteristic, request, *, response):
        client.sent.append(request)
        client.write_responses.append(response)
        operation = next(
            item for item in ReadOperation if request == build_read_request(item)
        )
        client.notifications[characteristic](characteristic, replies[operation])

    client.write_gatt_char = respond
    assert await read_baseline(hass, ADDRESS) == replies
    assert client.sent == [build_read_request(operation) for operation in ReadOperation]
    assert client.disconnect_called


async def test_runtime_read_requests_only_telemetry_and_operating_state(
    hass, fake_connection
):
    from custom_components.wendougee_data._protocol.crc import append_crc
    from tests.test_telemetry import TELEMETRY_RESPONSE

    client, _ = fake_connection
    replies = {
        ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
        ReadOperation.OPERATING_STATE: append_crc(
            b"\x01\x01\x03" + (16).to_bytes(3, "little")
        ),
    }

    async def respond(characteristic, request, *, response):
        client.sent.append(request)
        client.write_responses.append(response)
        operation = next(
            item for item in replies if request == build_read_request(item)
        )
        client.notifications[characteristic](characteristic, replies[operation])

    client.write_gatt_char = respond
    telemetry, state = await read_runtime(hass, ADDRESS)
    assert telemetry.pressure_bar == 8.7
    assert state.state == "manual"
    assert client.sent == [
        build_read_request(ReadOperation.TELEMETRY),
        build_read_request(ReadOperation.OPERATING_STATE),
    ]
    assert client.disconnect_called


async def test_coordinator_initializes_details_then_uses_runtime_reads(hass):
    from custom_components.wendougee_data._protocol.crc import append_crc
    from custom_components.wendougee_data._protocol.state import (
        decode_operating_state,
    )
    from tests.test_reads import register_response
    from tests.test_telemetry import TELEMETRY_RESPONSE

    values = [0] * 37
    values[0], values[1], values[2] = 55, 125, 4
    values[6], values[7] = 1, 0
    values[8], values[9] = 125, 94
    values[17], values[19], values[22] = 315, 85, 1
    idle = append_crc(b"\x01\x01\x03" + bytes(3))
    manual = append_crc(b"\x01\x01\x03" + (16).to_bytes(3, "little"))
    frames = {
        ReadOperation.TELEMETRY: TELEMETRY_RESPONSE,
        ReadOperation.CONFIGURATION: register_response(values),
        ReadOperation.WATER_ALARM_ENABLED: register_response([1]),
        ReadOperation.OPERATING_STATE: idle,
    }
    configured = entry()
    configured.add_to_hass(hass)
    coordinator = WendougeeCoordinator(hass, configured)

    with (
        patch(
            "custom_components.wendougee_data.coordinator.read_baseline",
            new_callable=AsyncMock,
            return_value=frames,
        ) as baseline,
        patch(
            "custom_components.wendougee_data.coordinator.read_runtime",
            new_callable=AsyncMock,
            return_value=(TELEMETRY, decode_operating_state(manual)),
        ) as runtime,
    ):
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert coordinator.configuration.brew_target_celsius == 94
        assert coordinator.configuration.steam_heating_enabled is False
        assert coordinator.water_alarm_enabled is True
        assert coordinator.operating_state.state == "idle"
        baseline.assert_awaited_once_with(hass, ADDRESS)
        runtime.assert_not_awaited()

        await coordinator.async_refresh()
        assert coordinator.operating_state.state == "manual"
        runtime.assert_awaited_once_with(hass, ADDRESS)

        coordinator._runtime_polls_since_configuration = 19
        await coordinator.async_refresh()
        assert baseline.await_count == 2
        assert coordinator.operating_state.state == "idle"

        coordinator.last_error = "read_failed"
        assert await coordinator.async_read_baseline() == frames
        assert baseline.await_count == 3
        assert coordinator.last_error is None


@pytest.mark.parametrize("properties", [{"notify"}, {"write"}])
async def test_invalid_gatt_properties_disconnect_without_request(
    hass, fake_connection, properties
):
    from custom_components.wendougee_data._protocol.const import (
        MODBUS_CHARACTERISTIC_UUID,
    )

    client, _ = fake_connection
    client.services.get_characteristic(
        MODBUS_CHARACTERISTIC_UUID
    ).properties = properties
    with pytest.raises(ValueError):
        await read_telemetry(hass, ADDRESS)
    assert client.disconnect_called
    assert client.sent == []


async def test_cleanup_failure_does_not_skip_disconnect(hass, fake_connection):
    client, _ = fake_connection
    client.fail_stop = True
    with pytest.raises(ConnectionError, match="cleanup failed"):
        await read_telemetry(hass, ADDRESS)
    assert client.disconnect_called
    assert len(client.stopped) == 2


async def test_disconnect_while_reading_is_not_accepted_as_a_sample(
    hass, fake_connection
):
    client, _ = fake_connection
    client.trigger_disconnect = True
    with pytest.raises(ConnectionError):
        await read_telemetry(hass, ADDRESS)
    assert client.disconnect_called


async def test_unload_cancels_inflight_poll_and_waits_for_cleanup(hass):
    configured = entry()
    configured.add_to_hass(hass)
    coordinator = WendougeeCoordinator(hass, configured)
    started, cleaned = asyncio.Event(), asyncio.Event()

    async def wait_for_cancel(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with patch(
        "custom_components.wendougee_data.coordinator.read_baseline",
        side_effect=wait_for_cancel,
    ):
        task = asyncio.create_task(coordinator.async_refresh())
        await started.wait()
        await coordinator.async_shutdown()
        assert cleaned.is_set()
        assert task.done()
        assert coordinator.stopped


async def test_scheduled_poll_uses_fresh_read_and_stops_after_unload(hass, freezer):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from .test_integration import BASELINE_FRAMES, IDLE_STATE, TELEMETRY

    configured = entry()
    configured.add_to_hass(hass)
    with (
        patch(
            "custom_components.wendougee_data.coordinator.read_baseline",
            new_callable=AsyncMock,
            return_value=BASELINE_FRAMES,
        ) as baseline,
        patch(
            "custom_components.wendougee_data.coordinator.read_runtime",
            new_callable=AsyncMock,
            return_value=(TELEMETRY, IDLE_STATE),
        ) as runtime,
    ):
        assert await hass.config_entries.async_setup(configured.entry_id)
        await hass.async_block_till_done()
        assert baseline.call_count == 1
        runtime.assert_not_awaited()
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert baseline.call_count == 1
        assert runtime.call_count == 1
        await hass.config_entries.async_unload(configured.entry_id)
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert baseline.call_count == 1
        assert runtime.call_count == 1
