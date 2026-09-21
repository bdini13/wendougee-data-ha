"""Conservative telemetry polling; no persistent connection or command retries."""

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ._protocol.reads import ReadOperation
from ._protocol.telemetry import Telemetry
from .bluetooth import read_baseline, read_telemetry
from .const import DEFAULT_POLL_INTERVAL, MAX_POLL_INTERVAL, MIN_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WendougeeCoordinator(DataUpdateCoordinator[Telemetry]):
    """Own HA polling/availability while each read owns a short BLE session."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = max(
            MIN_POLL_INTERVAL,
            min(
                MAX_POLL_INTERVAL,
                int(entry.data.get("poll_interval", DEFAULT_POLL_INTERVAL)),
            ),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Wendougee DATA",
            update_interval=timedelta(seconds=interval),
        )
        self.address = entry.data[CONF_ADDRESS]
        self.stopped = False
        self.last_error: str | None = None
        self._poll_task: asyncio.Task | None = None
        self._connection_lock = asyncio.Lock()

    async def _async_update_data(self) -> Telemetry:
        """Return a fresh sample or a privacy-safe failure, never a stale success."""
        async with self._connection_lock:
            if self.stopped:
                raise UpdateFailed("Integration stopped")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(40):
                    data = await read_telemetry(self.hass, self.address)
                self.last_error = None
                return data
            except Exception:
                # Backend exception text can contain addresses/names; do not forward it.
                self.last_error = "read_failed"
                raise UpdateFailed(
                    "Unable to obtain a valid telemetry sample"
                ) from None
            finally:
                self._poll_task = None

    async def async_read_baseline(self) -> dict[ReadOperation, bytes]:
        """Serialize one explicit baseline capture against scheduled polling."""
        async with self._connection_lock:
            if self.stopped:
                raise RuntimeError("Integration stopped")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(70):
                    return await read_baseline(self.hass, self.address)
            finally:
                self._poll_task = None

    async def async_shutdown(self) -> None:
        """Cancel future polls and await an in-flight session's cleanup on unload."""
        self.stopped = True
        await super().async_shutdown()
        task = self._poll_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
