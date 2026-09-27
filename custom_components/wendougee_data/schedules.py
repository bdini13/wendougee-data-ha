"""Daily local-time edges from existing helpers; no startup catch-up or retries."""

import asyncio
from contextlib import suppress
from datetime import datetime, time, timedelta

from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from ._protocol.controls import BoilerSetting
from .const import device_id
from .control import execute_boiler, verify_idle

BOILERS = {"brew": BoilerSetting.BREW_ENABLED, "steam": BoilerSetting.STEAM_ENABLED}


def helper(boiler, suffix):
    domain = "input_boolean" if suffix == "schedule_enabled" else "input_datetime"
    return f"{domain}.espresso_{boiler}_{suffix}"


class BoilerSchedules:
    """Only future clock edges can request a verified boiler enable transaction.

    Pending markers are written before hardware access and survive process death.
    A separate date per edge prevents duplicate fall-back-hour execution. Neither
    marker changes live boiler state or automatically re-enables a paused helper.
    """

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.store = Store(
            self.hass,
            1,
            f"wendougee_data.schedules.{device_id(coordinator.address)}",
            private=True,
        )
        self.pending = dict.fromkeys(BOILERS, False)
        self.last_attempts = {}
        self.last_result = dict.fromkeys(BOILERS, "not_run")
        self.last_verified = dict.fromkeys(BOILERS, None)
        self._timers = {}
        self._unsubscribe = None
        self._tasks = set()
        self._running = set()
        self.stopped = False

    async def async_load(self):
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.pending = {b: bool(saved.get("pending", {}).get(b)) for b in BOILERS}
            self.last_attempts = dict(saved.get("last_attempts", {}))
            for b in BOILERS:
                self.last_result[b] = saved.get("last_result", {}).get(b, "not_run")
                self.last_verified[b] = saved.get("last_verified", {}).get(b)

    async def _save(self, pending):
        await self.store.async_save(
            {
                "pending": dict(pending),
                "last_attempts": dict(self.last_attempts),
                "last_result": dict(self.last_result),
                "last_verified": dict(self.last_verified),
            }
        )
        self.pending = pending

    def _times(self, boiler):
        try:
            times = [
                time.fromisoformat(self.hass.states.get(helper(boiler, edge)).state)
                for edge in ("on_time", "off_time")
            ]
        except (ValueError, AttributeError):
            return None
        if times[0] == times[1] or any(t.tzinfo is not None for t in times):
            return None
        return times

    def _enabled(self, boiler):
        return self.hass.states.is_state(helper(boiler, "schedule_enabled"), "on")

    def _spawn(self, coroutine):
        task = self.hass.async_create_task(coroutine, "WENDOUGEE DATA S schedule edge")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @callback
    def _refresh(self, _event=None):
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        if (
            self.stopped
            or self.coordinator.entry.options.get("allow_boiler_control") is not True
        ):
            return
        for boiler in BOILERS:
            times = self._times(boiler)
            if not self._enabled(boiler):
                continue
            if self.pending[boiler]:
                self._spawn(self._pause(boiler))
                continue
            if times is None:
                continue  # Incomplete startup helpers never cause an action.
            for enabled, at in zip((True, False), times, strict=True):

                @callback
                def fire(_now, boiler=boiler, enabled=enabled):
                    self._spawn(self.async_run(boiler, enabled))

                self._timers[(boiler, enabled)] = async_track_time_change(
                    self.hass,
                    fire,
                    hour=at.hour,
                    minute=at.minute,
                    second=at.second,
                )
        self.coordinator.async_update_listeners()

    def status(self, boiler):
        """Local scheduler health remains readable during a BLE outage."""
        if boiler in self._running:
            return "executing"
        if self.pending[boiler]:
            return "check_machine"
        if (
            not self._enabled(boiler)
            and self.last_result[boiler] == "paused_check_machine"
        ):
            return "paused"
        if not self._enabled(boiler):
            return "disabled"
        if self.coordinator.entry.options.get("allow_boiler_control") is not True:
            return "control_disabled"
        if self._times(boiler) is None:
            return "invalid_times"
        if (
            self.coordinator.profile_start_locked
            or self.coordinator.cleaning_start_locked
        ):
            return "blocked"
        if len(self.hass.config_entries.async_entries("wendougee_data")) != 1:
            return "blocked"
        return "armed" if (boiler, True) in self._timers else "not_listening"

    def next_edge(self, boiler):
        """Display the next eligible edge, using HA's DST-aware time matcher.

        This is informational only: it cannot enqueue or execute an action.
        Already-attempted local dates are skipped just like the action guard.
        """
        if self.status(boiler) != "armed":
            return None, None
        now = dt_util.now()
        candidates = []
        for action, at in zip(("on", "off"), self._times(boiler), strict=True):
            start = now + timedelta(microseconds=1)
            candidate = dt_util.find_next_time_expression_time(
                start, [at.second], [at.minute], [at.hour]
            )
            if (
                self.last_attempts.get(f"{boiler}_{action}")
                == candidate.date().isoformat()
            ):
                start = datetime.combine(
                    candidate.date() + timedelta(days=1), time(), tzinfo=now.tzinfo
                )
                candidate = dt_util.find_next_time_expression_time(
                    start, [at.second], [at.minute], [at.hour]
                )
            candidates.append((candidate, action))
        at, action = min(candidates, key=lambda item: item[0].timestamp())
        return action, at.isoformat()

    async def async_setup(self):
        await self.async_load()
        self._unsubscribe = async_track_state_change_event(
            self.hass,
            [
                helper(b, s)
                for b in BOILERS
                for s in ("schedule_enabled", "on_time", "off_time")
            ],
            self._refresh,
        )
        self._refresh()

    def diagnostics(self):
        return {
            b: {
                "enabled": self._enabled(b),
                "listening": (b, True) in self._timers and (b, False) in self._timers,
                "pending_uncertainty": self.pending[b],
                "last_result": self.last_result[b],
                "last_verified_at": self.last_verified[b],
                "status": self.status(b),
                "next_action": self.next_edge(b)[0],
                "next_action_at": self.next_edge(b)[1],
                "on_time": self.hass.states.get(helper(b, "on_time")).state
                if self.hass.states.get(helper(b, "on_time"))
                else None,
                "off_time": self.hass.states.get(helper(b, "off_time")).state
                if self.hass.states.get(helper(b, "off_time"))
                else None,
            }
            for b in BOILERS
        }

    async def _pause(self, boiler):
        self._running.discard(boiler)
        self.last_result[boiler] = "paused_check_machine"
        # Notification metadata must not weaken the existing uncertainty guard.
        with suppress(OSError):
            await self._save(dict(self.pending))
        self.coordinator.async_update_listeners()
        persistent_notification.async_create(
            self.hass,
            f"The {boiler} schedule is paused: its action was not verified. "
            "The boiler may still be on. Check the machine physically. "
            "No retry or stop was sent. If uncertainty is locked, use "
            "Acknowledge boiler schedule uncertainty with "
            "MACHINE CHECKED, then re-enable the schedule. No missed edge is replayed.",
            title="WENDOUGEE DATA S schedule needs attention",
            notification_id=f"wendougee_{boiler}_schedule",
        )
        # Pending state still blocks an uncertain repeat if the helper is missing.
        with suppress(HomeAssistantError):
            await self.hass.services.async_call(
                "input_boolean",
                "turn_off",
                {"entity_id": helper(boiler, "schedule_enabled")},
                blocking=True,
            )

    def _at_edge(self, boiler, enabled):
        times = self._times(boiler)
        if times is None:
            return False
        now = dt_util.now()
        at = times[0 if enabled else 1]
        edge = datetime.combine(now.date(), at, tzinfo=now.tzinfo)
        return 0 <= (now - edge).total_seconds() < 60

    async def async_run(self, boiler, enabled):
        c = self.coordinator
        if self.stopped or c.stopped or not self._enabled(boiler):
            return
        acquired = False
        try:
            c._require_control("allow_boiler_control")
            if len(self.hass.config_entries.async_entries("wendougee_data")) != 1:
                raise HomeAssistantError("Shared helpers require exactly one machine")
            if (
                self.pending[boiler]
                or c.profile_start_locked
                or c.cleaning_start_locked
            ):
                raise HomeAssistantError("Previous control is uncertain")
            if not self._at_edge(boiler, enabled):
                return  # No startup catch-up, stale callback or manual late execution.
            async with asyncio.timeout(5):
                await c._connection_lock.acquire()
            acquired = True
            if (
                self.stopped
                or c.stopped
                or not self._enabled(boiler)
                or not self._at_edge(boiler, enabled)
            ):
                return
            c._require_control("allow_boiler_control")
            if (
                self.pending[boiler]
                or c.profile_start_locked
                or c.cleaning_start_locked
            ):
                raise HomeAssistantError("Previous control is uncertain")
            edge_key = f"{boiler}_{'on' if enabled else 'off'}"
            day = dt_util.now().date().isoformat()
            if self.last_attempts.get(edge_key) == day:
                return
            self._running.add(boiler)
            self.pending[boiler] = True
            self.last_attempts[edge_key] = day
            await self._save(dict(self.pending))
            c._poll_task = asyncio.current_task()
            async with asyncio.timeout(90):
                configuration = await execute_boiler(
                    self.hass, c.address, BOILERS[boiler], enabled
                )
            if getattr(configuration, f"{boiler}_heating_enabled") is not enabled:
                raise HomeAssistantError("Requested state not verified")
            c.configuration = configuration
            c.async_set_updated_data(c.data)
            self.last_result[boiler] = "verified_on" if enabled else "verified_off"
            self.last_verified[boiler] = dt_util.utcnow().isoformat()
            await self._save({**self.pending, boiler: False})
            persistent_notification.async_dismiss(
                self.hass, f"wendougee_{boiler}_schedule"
            )
        except asyncio.CancelledError:
            await self._pause(boiler)
            raise
        except Exception:
            if self.pending[boiler]:
                c.async_set_update_error(
                    UpdateFailed("Scheduled boiler result uncertain")
                )
            await self._pause(boiler)
        finally:
            self._running.discard(boiler)
            c.async_update_listeners()
            if acquired:
                c._poll_task = None
                c._connection_lock.release()

    async def async_acknowledge(self, boiler):
        c = self.coordinator
        c._require_control("allow_boiler_control")
        if c._connection_lock.locked():
            raise HomeAssistantError("Bluetooth operation busy")
        async with c._connection_lock:
            c._poll_task = asyncio.current_task()
            try:
                async with asyncio.timeout(30):
                    await verify_idle(self.hass, c.address)
                await self._save({**self.pending, boiler: False})
            except Exception:
                raise HomeAssistantError(
                    "Unable to verify idle; schedule remains locked"
                ) from None
            finally:
                c._poll_task = None
        # Owner must separately re-enable the helper; this never heats anything.
        self.last_result[boiler] = "acknowledged_still_disabled"
        await self._save(dict(self.pending))
        c.async_update_listeners()

    async def async_shutdown(self):
        self.stopped = True
        self._refresh()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
