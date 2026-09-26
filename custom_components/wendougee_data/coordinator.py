"""Conservative telemetry polling; no persistent connection or command retries."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ._protocol.control_session import ControlRejected
from ._protocol.reads import ReadOperation
from ._protocol.state import (
    Configuration,
    OperatingState,
    decode_configuration,
    decode_operating_state,
    decode_water_alarm_enabled,
)
from ._protocol.telemetry import Telemetry, parse_telemetry_response
from .activity import ActivityTracker
from .bluetooth import read_baseline, read_runtime
from .const import (
    CONF_CAPTURE_BASELINE,
    DEFAULT_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    device_id,
)
from .control import execute_boiler, execute_cleaning, execute_profile, verify_idle
from .fast_capture import (
    RuntimeTrace,
    SamplingBenchmark,
    benchmark_runtime_sampling,
    capture_runtime_trace,
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
            name="WENDOUGEE DATA S",
            update_interval=timedelta(seconds=interval),
        )
        self.address = entry.data[CONF_ADDRESS]
        self.activity = ActivityTracker(hass, device_id(self.address))
        self.stopped = False
        self.last_error: str | None = None
        self.last_successful_poll_utc: datetime | None = None
        self.last_failed_poll_utc: datetime | None = None
        self.successful_polls_since_load = 0
        self.failed_polls_since_load = 0
        self.consecutive_failed_polls = 0
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
        self.fast_sample_hz: float | None = None
        self.last_sampling_benchmark: SamplingBenchmark | None = None
        self.entry = entry
        self.profile_start_locked = False
        self.cleaning_start_locked = False
        self._control_store = Store(
            hass, 1, f"wendougee_data.controls.{device_id(self.address)}", private=True
        )

    async def async_load_control_state(self) -> None:
        """An uncertain toggle stays blocked across reloads and restarts."""
        saved = await self._control_store.async_load()
        self.profile_start_locked = bool(saved and saved.get("profile_start_locked"))
        self.cleaning_start_locked = bool(saved and saved.get("cleaning_start_locked"))

    async def _save_profile_lock(self, locked: bool) -> None:
        # A failed disk write must never unlock the in-memory guard.
        if locked:
            self.profile_start_locked = True
        await self._control_store.async_save(
            {
                "profile_start_locked": locked,
                "cleaning_start_locked": self.cleaning_start_locked,
            }
        )
        self.profile_start_locked = locked
        self.async_update_listeners()

    def _require_control(self, option: str) -> None:
        if self.entry.options.get(option) is not True:
            raise HomeAssistantError(
                "This control is not enabled in integration options"
            )
        if self.stopped:
            raise HomeAssistantError("Integration stopped")

    async def async_set_boiler(self, setting, enabled: bool) -> None:
        """Publish feedback only after a verified complete configuration readback."""
        self._require_control("allow_boiler_control")
        async with self._connection_lock:
            self._require_control("allow_boiler_control")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(90):
                    self.configuration = await execute_boiler(
                        self.hass, self.address, setting, enabled
                    )
                self.async_set_updated_data(self.data)
            except ControlRejected as error:
                raise HomeAssistantError(str(error)) from None
            except Exception:
                self.async_set_update_error(UpdateFailed("Control result uncertain"))
                raise HomeAssistantError(
                    "Boiler result uncertain; refresh and check the machine "
                    "before retrying"
                ) from None
            finally:
                self._poll_task = None

    async def async_start_profile(self) -> None:
        """Never queue a delayed start or repeat an uncertain toggle."""
        self._require_control("allow_profile_start")
        if self._connection_lock.locked():
            raise HomeAssistantError("Bluetooth operation busy; start was not queued")
        if self.profile_start_locked or self.cleaning_start_locked:
            raise HomeAssistantError(
                "Previous profile start is uncertain; inspect the machine "
                "and acknowledge it first"
            )
        async with self._connection_lock:
            self._poll_task = asyncio.current_task()
            try:
                # Persist before touching the machine: process death also locks retries.
                await self._save_profile_lock(True)
                async with asyncio.timeout(90):
                    telemetry, state = await execute_profile(self.hass, self.address)
                self.operating_state = state
                self.activity.observe(telemetry, state)
                await self._save_profile_lock(False)
                self.async_set_updated_data(telemetry)
            except ControlRejected as error:
                await self._save_profile_lock(False)
                raise HomeAssistantError(str(error)) from None
            except Exception:
                raise HomeAssistantError(
                    "Profile start result uncertain; further starts are locked. "
                    "Check the machine physically before acknowledging uncertainty."
                ) from None
            finally:
                self._poll_task = None

    async def async_acknowledge_profile_uncertainty(self) -> None:
        """Explicit acknowledgement also requires a new idle read; never writes."""
        self._require_control("allow_profile_start")
        async with self._connection_lock:
            self._require_control("allow_profile_start")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(30):
                    await verify_idle(self.hass, self.address)
                await self._save_profile_lock(False)
            except Exception:
                raise HomeAssistantError(
                    "Unable to verify idle; start remains locked"
                ) from None
            finally:
                self._poll_task = None

    async def _save_cleaning_lock(self, locked: bool) -> None:
        """Preserve both guards and never clear memory after a failed disk write."""
        if locked:
            self.cleaning_start_locked = True
        await self._control_store.async_save(
            {
                "profile_start_locked": self.profile_start_locked,
                "cleaning_start_locked": locked,
            }
        )
        self.cleaning_start_locked = locked
        self.async_update_listeners()

    def _observe_cleaning(self, telemetry, state, configuration) -> None:
        self.configuration = configuration
        self.operating_state = state
        self.activity.observe(telemetry, state)
        self.async_set_updated_data(telemetry)

    async def async_start_cleaning(self) -> dict:
        """Explicit attended start; persist uncertainty before the first command."""
        self._require_control("allow_cleaning_control")
        if self._connection_lock.locked():
            raise HomeAssistantError(
                "Bluetooth operation busy; cleaning was not queued"
            )
        if self.cleaning_start_locked or self.profile_start_locked:
            raise HomeAssistantError(
                "Previous control is uncertain; inspect the machine first"
            )
        async with self._connection_lock:
            self._poll_task = asyncio.current_task()
            try:
                await self._save_cleaning_lock(True)
                async with asyncio.timeout(180):
                    result = await execute_cleaning(
                        self.hass, self.address, self._observe_cleaning
                    )
                await self.activity.async_save()
                await self._save_cleaning_lock(False)
                return result
            except ControlRejected as error:
                await self._save_cleaning_lock(False)
                raise HomeAssistantError(str(error)) from None
            except Exception:
                self.async_set_update_error(UpdateFailed("Cleaning result uncertain"))
                raise HomeAssistantError(
                    "Cleaning result uncertain; further starts are locked. "
                    "Check the machine physically; no retry or stop pulse was sent."
                ) from None
            finally:
                self._poll_task = None

    async def async_acknowledge_cleaning_uncertainty(self) -> None:
        """Clear only on explicit physical-check acknowledgement and fresh idle."""
        self._require_control("allow_cleaning_control")
        if self._connection_lock.locked():
            raise HomeAssistantError("Bluetooth operation busy")
        async with self._connection_lock:
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(30):
                    await verify_idle(self.hass, self.address)
                await self._save_cleaning_lock(False)
            except Exception:
                raise HomeAssistantError(
                    "Unable to verify idle; cleaning remains locked"
                ) from None
            finally:
                self._poll_task = None

    def _record_poll_success(self) -> None:
        """Record privacy-safe health evidence for a completed coordinator poll."""
        self.last_successful_poll_utc = datetime.now(UTC)
        self.successful_polls_since_load += 1
        self.consecutive_failed_polls = 0
        self.last_error = None

    def _record_poll_failure(self) -> None:
        """Record a failed coordinator poll without retaining exception details."""
        self.last_failed_poll_utc = datetime.now(UTC)
        self.failed_polls_since_load += 1
        self.consecutive_failed_polls += 1
        self.last_error = "read_failed"

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
                self._record_poll_success()
                self.activity.observe(data, self.operating_state)
                return data
            except Exception:
                # Backend exception text can contain addresses/names; do not forward it.
                self._record_poll_failure()
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
                    self.activity.observe(data, self.operating_state)
                    self.async_set_updated_data(data)
                    return frames
            finally:
                self._poll_task = None

    async def async_benchmark_sampling(self) -> SamplingBenchmark:
        """Find the fastest clean bounded rate before enabling trace capture."""
        async with self._connection_lock:
            if self.stopped:
                raise RuntimeError("Integration stopped")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(90):
                    result = await benchmark_runtime_sampling(self.hass, self.address)
                self.last_sampling_benchmark = result
                self.fast_sample_hz = result.selected_hz
                return result
            finally:
                self._poll_task = None

    async def async_capture_runtime_trace(self, duration_seconds: int) -> RuntimeTrace:
        """Capture a bounded trace only after a clean rate benchmark."""
        if self.fast_sample_hz is None:
            raise RuntimeError("Run the read-only sampling benchmark first")
        async with self._connection_lock:
            if self.stopped:
                raise RuntimeError("Integration stopped")
            self._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(duration_seconds + 20):
                    trace = await capture_runtime_trace(
                        self.hass,
                        self.address,
                        duration_seconds=duration_seconds,
                        target_hz=self.fast_sample_hz,
                    )
                for sample in trace.samples:
                    self.activity.observe(
                        sample.telemetry,
                        sample.operating_state,
                        now=sample.observed_at_utc,
                    )
                if trace.samples:
                    latest = trace.samples[-1]
                    self.operating_state = latest.operating_state
                    self.last_error = None
                    self.async_set_updated_data(latest.telemetry)
                return trace
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
        await self.activity.async_save()
