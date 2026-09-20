"""Deterministic fake-transport tests. No Bluetooth imports or hardware I/O."""

import asyncio
import unittest

from wendougee_data.crc import append_crc
from wendougee_data.reads import DeviceException, ReadOperation, build_read_request
from wendougee_data.session import ReadSession, SessionUnavailable

from .test_reads import register_response


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.started = asyncio.Event()
        self.closed = False
        self.open_error = None
        self.close_error = None
        self.send_error = None
        self.reply = None

    async def open(self, on_data, on_disconnect):
        self.on_data = on_data
        self.on_disconnect = on_disconnect
        if self.open_error:
            raise self.open_error

    async def send(self, request):
        self.sent.append(request)
        self.started.set()
        if self.send_error:
            raise self.send_error
        if self.reply is not None:
            self.on_data(self.reply)

    async def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_are_serialized_and_frames_can_be_fragmented(self):
        transport = FakeTransport()
        async with ReadSession(transport) as session:
            first = asyncio.create_task(session.read(ReadOperation.WATER_ALARM_ENABLED))
            await transport.started.wait()
            second = asyncio.create_task(session.read(ReadOperation.CONFIGURATION))
            await asyncio.sleep(0)
            self.assertEqual(len(transport.sent), 1)
            frame = register_response([1])
            transport.on_data(frame[:3])
            self.assertFalse(first.done())
            transport.on_data(frame[3:])
            self.assertEqual(await first, frame)
            await asyncio.sleep(0)
            self.assertEqual(len(transport.sent), 2)
            config = register_response([0] * 37)
            transport.on_data(config)
            self.assertEqual(await second, config)
        self.assertTrue(transport.closed)
        self.assertEqual(
            transport.sent,
            [
                build_read_request(ReadOperation.WATER_ALARM_ENABLED),
                build_read_request(ReadOperation.CONFIGURATION),
            ],
        )

    async def test_exception_reply_fails_promptly_and_session_cannot_be_reused(self):
        transport = FakeTransport()
        transport.reply = append_crc(b"\x01\x83\x02")
        async with ReadSession(transport) as session:
            with self.assertRaises(DeviceException):
                await session.read(ReadOperation.TELEMETRY)
            with self.assertRaises(SessionUnavailable):
                await session.read(ReadOperation.TELEMETRY)
        self.assertEqual(len(transport.sent), 1)

    async def test_timeout_quarantines_late_reply_and_requires_new_session(self):
        transport = FakeTransport()
        async with ReadSession(transport, timeout=0.01) as session:
            with self.assertRaises(TimeoutError):
                await session.read(ReadOperation.WATER_ALARM_ENABLED)
            transport.on_data(register_response([1]))
            with self.assertRaises(SessionUnavailable):
                await session.read(ReadOperation.WATER_ALARM_ENABLED)
        fresh = FakeTransport()
        fresh.reply = register_response([0])
        async with ReadSession(fresh) as session:
            self.assertEqual(
                await session.read(ReadOperation.WATER_ALARM_ENABLED), fresh.reply
            )

    async def test_disconnect_immediately_fails_pending_and_queued_read(self):
        transport = FakeTransport()
        async with ReadSession(transport) as session:
            first = asyncio.create_task(session.read(ReadOperation.TELEMETRY))
            await transport.started.wait()
            second = asyncio.create_task(session.read(ReadOperation.CONFIGURATION))
            transport.on_disconnect()
            for task in [first, second]:
                with self.assertRaises(SessionUnavailable):
                    await task
            self.assertEqual(len(transport.sent), 1)

    async def test_cancelled_inflight_read_invalidates_session(self):
        transport = FakeTransport()
        async with ReadSession(transport) as session:
            task = asyncio.create_task(session.read(ReadOperation.TELEMETRY))
            await transport.started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaises(SessionUnavailable):
                await session.read(ReadOperation.TELEMETRY)

    async def test_cancelling_queued_reader_does_not_cancel_active_reader(self):
        transport = FakeTransport()
        async with ReadSession(transport) as session:
            first = asyncio.create_task(session.read(ReadOperation.WATER_ALARM_ENABLED))
            await transport.started.wait()
            queued = asyncio.create_task(session.read(ReadOperation.CONFIGURATION))
            await asyncio.sleep(0)
            queued.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await queued
            transport.on_data(register_response([1]))
            await first
            self.assertEqual(len(transport.sent), 1)

    async def test_duplicate_coalesced_partial_trailer_and_mismatched_frames_rejected(
        self,
    ):
        good = register_response([1])
        for reply in [
            good + good,
            good + b"\x01",
            register_response([0] * 37),
            append_crc(b"\x01\x01\x03\x00\x00\x00"),
        ]:
            with self.subTest(reply=reply):
                transport = FakeTransport()
                transport.reply = reply
                async with ReadSession(transport) as session:
                    with self.assertRaises(ValueError):
                        await session.read(ReadOperation.WATER_ALARM_ENABLED)
                    with self.assertRaises(SessionUnavailable):
                        await session.read(ReadOperation.WATER_ALARM_ENABLED)

    async def test_unsolicited_idle_data_blocks_next_request(self):
        transport = FakeTransport()
        async with ReadSession(transport) as session:
            transport.on_data(register_response([1]))
            with self.assertRaises(SessionUnavailable):
                await session.read(ReadOperation.WATER_ALARM_ENABLED)
        self.assertEqual(transport.sent, [])

    async def test_setup_failure_cleanup_does_not_mask_original_error(self):
        transport = FakeTransport()
        transport.open_error = RuntimeError("setup failed")
        transport.close_error = RuntimeError("cleanup failed")
        with self.assertRaisesRegex(RuntimeError, "setup failed"):
            async with ReadSession(transport):
                self.fail("must not enter")
        self.assertTrue(transport.closed)

    async def test_send_failure_and_cleanup_failure_keep_original_error(self):
        transport = FakeTransport()
        transport.send_error = RuntimeError("send failed")
        transport.close_error = RuntimeError("cleanup failed")
        with self.assertRaisesRegex(RuntimeError, "send failed"):
            async with ReadSession(transport) as session:
                await session.read(ReadOperation.TELEMETRY)
        self.assertTrue(transport.closed)

    async def test_cleanup_failure_is_reported_without_primary_error(self):
        transport = FakeTransport()
        transport.close_error = RuntimeError("cleanup failed")
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            async with ReadSession(transport):
                pass

    async def test_operations_outside_session_and_reopening_are_rejected(self):
        session = ReadSession(FakeTransport())
        with self.assertRaises(SessionUnavailable):
            await session.read(ReadOperation.TELEMETRY)
        async with session:
            with self.assertRaisesRegex(ValueError, "allowlisted"):
                await session.read("write")
        with self.assertRaises(SessionUnavailable):
            async with session:
                pass

    async def test_invalid_timeout_rejected(self):
        for value in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                ReadSession(FakeTransport(), timeout=value)

    async def test_hung_setup_is_bounded_and_cleaned_up(self):
        transport = FakeTransport()

        async def hung_open(_data, _disconnect):
            await asyncio.Event().wait()

        transport.open = hung_open
        with self.assertRaises(TimeoutError):
            async with ReadSession(transport, timeout=0.01):
                self.fail("must not enter")
        self.assertTrue(transport.closed)

    async def test_hung_send_is_bounded_and_invalidates_session(self):
        transport = FakeTransport()

        async def hung_send(_request):
            await asyncio.Event().wait()

        transport.send = hung_send
        async with ReadSession(transport, timeout=0.01) as session:
            with self.assertRaises(TimeoutError):
                await session.read(ReadOperation.TELEMETRY)
            with self.assertRaises(SessionUnavailable):
                await session.read(ReadOperation.TELEMETRY)

    async def test_hung_cleanup_is_bounded(self):
        transport = FakeTransport()

        async def hung_close():
            await asyncio.Event().wait()

        transport.close = hung_close
        with self.assertRaises(TimeoutError):
            async with ReadSession(transport, timeout=0.01):
                pass

    async def test_second_callback_before_result_is_consumed_invalidates_read(self):
        transport = FakeTransport()

        async def duplicate_reply(_request):
            transport.on_data(register_response([1]))
            transport.on_data(register_response([1]))

        transport.send = duplicate_reply
        async with ReadSession(transport) as session:
            with self.assertRaises(SessionUnavailable):
                await session.read(ReadOperation.WATER_ALARM_ENABLED)

    async def test_bad_crc_does_not_deliver_data(self):
        transport = FakeTransport()
        frame = register_response([1])
        transport.reply = frame[:-1] + bytes([frame[-1] ^ 1])
        async with ReadSession(transport) as session:
            with self.assertRaisesRegex(ValueError, "CRC"):
                await session.read(ReadOperation.WATER_ALARM_ENABLED)

    async def test_empty_notifications_do_not_poison_session(self):
        transport = FakeTransport()
        transport.reply = register_response([1])
        async with ReadSession(transport) as session:
            transport.on_data(b"")
            self.assertEqual(
                await session.read(ReadOperation.WATER_ALARM_ENABLED), transport.reply
            )
