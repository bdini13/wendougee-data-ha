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
from ._protocol.state import (
    Configuration,
    OperatingState,
    decode_configuration,
    decode_operating_state,
    decode_water_alarm_enabled,
)
from ._protocol.telemetry import Telemetry, parse_telemetry_response
from .bluetooth import read_baseline, read_runtime
from .const import (
    CONF_CAPTURE_BASELINE,
    DEFAULT_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
CONFIGURATION_REFRESH_POLLS = 20


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
        self.configuration: Configuration | None = None
        self.water_alarm_enabled: bool | None = None
        self.operating_state: OperatingState | None = None
        self._runtime_polls_since_configuration = 0
        self._cache_initial_baseline = bool(
            entry.data.get(CONF_CAPTURE_BASELINE, False)
        )
        self._cached_baseline_frames: dict[ReadOperation, bytes] | None = None
        self._poll_task: asyncio.Task | None = None
        self._connection_lock = asyncio.Lock()

    def _apply_baseline(self, frames: dict[ReadOperation, bytes]) -> Telemetry:
        """Decode one complete fixed baseline only after every read succeeded."""
        telemetry = parse_telemetry_response(frames[ReadOperation.TELEMETRY])
        configuration = decode_configuration(frames[ReadOperation.CONFIGURATION])
        water_alarm_enabled = decode_water_alarm_enabled(
            frames[ReadOperation.WATER_ALARM_ENABLED]
        )
        operating_state = decode_operating_state(frames[ReadOperation.OPERATING_STATE])
        self.configuration = configuration
        self.water_alarm_enabled = water_alarm_enabled
        self.operating_state = operating_state
        self._runtime_polls_since_configuration = 0
        return telemetry

    async def _async_update_data(self) -> Telemetry:
        """Return a fresh sample or a privacy-safe failure, never a stale success."""
        async with self._connection_lock:
            if self.stopped:
                raise UpdateFailed("Integration stopped")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(70):
                    initial_baseline = self.configuration is None
                    if (
                        initial_baseline
                        or self._runtime_polls_since_configuration + 1
                        >= CONFIGURATION_REFRESH_POLLS
                    ):
                        frames = await read_baseline(self.hass, self.address)
                        data = self._apply_baseline(frames)
                        if initial_baseline and self._cache_initial_baseline:
                            self._cached_baseline_frames = dict(frames)
                    else:
                        data, self.operating_state = await read_runtime(
                            self.hass, self.address
                        )
                        self._runtime_polls_since_configuration += 1
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

    def take_cached_baseline_frames(self) -> dict[ReadOperation, bytes] | None:
        """Return one completed baseline to the private writer, then forget it."""
        frames = self._cached_baseline_frames
        self._cached_baseline_frames = None
        return frames

    async def async_read_baseline(self) -> dict[ReadOperation, bytes]:
        """Serialize one explicit baseline capture against scheduled polling."""
        async with self._connection_lock:
            if self.stopped:
                raise RuntimeError("Integration stopped")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(70):
                    frames = await read_baseline(self.hass, self.address)
                    data = self._apply_baseline(frames)
                    self.last_error = None
                    self.async_set_updated_data(data)
                    return frames
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
