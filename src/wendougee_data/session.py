"""Serialized, allowlisted read sessions over an injected notification transport.

No scanner, Bluetooth import, automatic reconnect, control, or background task.
Each instance owns one connection epoch and cannot be reopened after closure.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from enum import Enum
from types import TracebackType
from typing import Protocol

from .reads import (
    ReadOperation,
    ReadResponseStream,
    build_read_request,
    validate_read_response,
)


class ReadTransport(Protocol):
    """Adapter owns connection/subscriptions; callbacks run on the session loop.

    open() returns only after notifications are ready. close() must also clean
    up a partially failed open. A new session must use a fresh connection.
    """

    async def open(
        self, on_data: Callable[[bytes], None], on_disconnect: Callable[[], None]
    ) -> None:
        """Connect and finish notification setup before returning."""
        ...

    async def send(self, request: bytes) -> None:
        """Transmit a session-built read request; do not retry it implicitly."""
        ...

    async def close(self) -> None:
        """Release subscriptions/connection, including after partial open failure."""
        ...


class SessionUnavailable(ConnectionError):
    """Session is closed, disconnected, or cannot safely correlate more reads."""


class ReadSession:
    """One in-flight read; any transaction failure quarantines the session.

    Same-shaped unsolicited responses cannot be distinguished on Modbus RTU.
    Serialization and failure quarantine reduce ambiguity, not eliminate it.
    """

    def __init__(self, transport: ReadTransport, *, timeout: float = 8.0) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self._transport = transport
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._stream = ReadResponseStream()
        self._pending: asyncio.Future[bytes] | None = None
        self._operation: Enum | None = None
        self._failure: BaseException | None = None
        self._active = False
        self._used = False

    async def __aenter__(self) -> ReadSession:
        if self._used:
            raise SessionUnavailable("create a fresh session and connection")
        self._used = True
        try:
            async with asyncio.timeout(self._timeout):
                await self._transport.open(self._on_data, self._on_disconnect)
            self._active = True
            self._require_active()
        except BaseException as error:
            self._invalidate(error)
            await self._close(error)
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._close(exc)

    async def _close(self, primary_error: BaseException | None) -> None:
        self._active = False
        self._invalidate(SessionUnavailable("session closed"))
        try:
            async with asyncio.timeout(self._timeout):
                await self._transport.close()
        except Exception:
            if primary_error is None:
                raise
            primary_error.add_note(
                "Transport cleanup also failed; connection unverified."
            )

    def _require_active(self) -> None:
        if not self._active or self._failure is not None:
            raise SessionUnavailable("session unavailable; use a fresh connection")

    def _invalidate(self, error: BaseException) -> None:
        if self._failure is None:
            self._failure = error
        if self._pending is not None and not self._pending.done():
            self._pending.set_exception(error)

    def _on_disconnect(self) -> None:
        self._invalidate(SessionUnavailable("transport disconnected"))

    def _on_data(self, fragment: bytes) -> None:
        if not fragment or self._failure is not None:
            return
        pending = self._pending
        if pending is None or pending.done() or self._operation is None:
            self._invalidate(ValueError("unsolicited or duplicate response"))
            return
        try:
            frames = self._stream.feed(fragment)
            if not frames:
                return
            if len(frames) != 1 or self._stream.pending_bytes:
                raise ValueError("multiple responses or unexpected trailing data")
            validate_read_response(frames[0], self._operation)
        except ValueError as error:
            self._invalidate(error)
        else:
            pending.set_result(frames[0])

    async def read(self, operation: ReadOperation) -> bytes:
        """Return a validated complete frame, with no automatic retries.

        Cancelling a queued reader does not invalidate someone else's active
        read. Cancelling after it acquires the lock does invalidate the session.
        """
        return await self._exchange(build_read_request(operation), operation)

    async def _exchange(self, request: bytes, operation: Enum) -> bytes:
        """Share connection-epoch lifecycle with narrowly allowlisted subclasses."""
        async with self._lock:
            self._require_active()
            self._operation = operation
            pending = asyncio.get_running_loop().create_future()
            self._pending = pending
            try:
                async with asyncio.timeout(self._timeout):
                    await self._transport.send(request)
                    frame = await pending
                    self._require_active()
                    return frame
            except BaseException as error:
                self._invalidate(error)
                raise
            finally:
                if not pending.done():
                    pending.cancel()
                elif not pending.cancelled():
                    pending.exception()  # Consume a simultaneous callback/send failure.
                self._pending = None
                self._operation = None
