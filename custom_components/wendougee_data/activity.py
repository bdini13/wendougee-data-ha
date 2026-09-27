"""Persist conservative activity observations derived from read-only polling."""

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ._protocol.state import OperatingState
from ._protocol.telemetry import Telemetry
from .const import DOMAIN
from .shot_journal import ShotJournal

STORAGE_VERSION = 1
# Conservative attribution policy, not machine timing limits. The reviewed
# 2 Hz trace settles 1.536 s after idle; ordinary 30 s polls cannot resolve this.
SHOT_TAIL_SECONDS = 5.0
SHOT_TAIL_MAX_SAMPLE_GAP_SECONDS = 2.0


class ActivityTracker:
    """Track only events actually observed by the polling coordinator.

    A short shot can occur entirely between polls. Names exposed by the integration
    therefore use "observed" and never claim these counters are exhaustive.
    """

    def __init__(self, hass: HomeAssistant, identity: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.activity.{identity}", private=True
        )
        self.observed_shots_total = 0
        self.observed_pumped_water_ml = 0.0
        self.last_shot_utc: datetime | None = None
        self.last_shot_volume_ml: int | None = None
        self.last_cleaning_utc: datetime | None = None
        self.shot_active = False
        self.cleaning_active = False
        self.journal = ShotJournal()
        self._initialized = False
        self._previous_volume_ml: int | None = None
        self._current_shot_peak_volume_ml = 0
        self._previous_observed_at: datetime | None = None
        self._previous_brew_time_seconds: float | None = None
        # Runtime-only: reload must not resume attributing old tails.
        self._shot_tail_started_at: datetime | None = None
        self._shot_tail_brew_time_seconds: float | None = None

    def _as_dict(self) -> dict[str, Any]:
        """Return the durable, identifier-free activity state."""
        return {
            "journal": self.journal.dump(),
            "observed_shots_total": self.observed_shots_total,
            "observed_pumped_water_ml": self.observed_pumped_water_ml,
            "last_shot_utc": (
                self.last_shot_utc.isoformat() if self.last_shot_utc else None
            ),
            "last_shot_volume_ml": self.last_shot_volume_ml,
            "last_cleaning_utc": (
                self.last_cleaning_utc.isoformat() if self.last_cleaning_utc else None
            ),
        }

    async def async_load(self) -> None:
        """Restore durable totals while leaving transition state uninitialized."""
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return
        self.journal.restore(data.get("journal"))
        shots = data.get("observed_shots_total")
        water = data.get("observed_pumped_water_ml")
        volume = data.get("last_shot_volume_ml")
        if isinstance(shots, int) and shots >= 0:
            self.observed_shots_total = shots
        if isinstance(water, int | float) and water >= 0:
            self.observed_pumped_water_ml = float(water)
        if isinstance(volume, int) and volume >= 0:
            self.last_shot_volume_ml = volume
        self.last_shot_utc = self._parse_datetime(data.get("last_shot_utc"))
        self.last_cleaning_utc = self._parse_datetime(data.get("last_cleaning_utc"))

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Accept only timezone-aware ISO timestamps from our private store."""
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None

    async def async_save(self) -> None:
        """Persist activity immediately; used for shutdown and deterministic tests."""
        await self._store.async_save(self._as_dict())

    def _schedule_save(self) -> None:
        """Coalesce writes caused by consecutive samples."""
        self._store.async_delay_save(self._as_dict, 1)

    def observe(
        self,
        telemetry: Telemetry,
        state: OperatingState,
        now: datetime | None = None,
        *,
        source: str = "poll",
    ) -> bool:
        """Observe one validated sample and return whether durable state changed."""
        observed_at = now or datetime.now(UTC)
        self.journal.observe(
            telemetry,
            state,
            observed_at,
            source=source,
            previous_active=self.shot_active,
            initialized=self._initialized,
        )
        shot_active = bool(
            state.profile_active or state.manual_active or state.free_variable_active
        )
        cleaning_active = state.cleaning_active
        volume_ml = telemetry.dispensed_volume_ml
        brew_time = telemetry.elapsed_brew_time_seconds
        sample_gap = (
            (observed_at - self._previous_observed_at).total_seconds()
            if self._previous_observed_at is not None
            else None
        )
        previous_brew_time = self._previous_brew_time_seconds
        self._previous_observed_at = observed_at
        self._previous_brew_time_seconds = brew_time

        if not self._initialized:
            self._initialized = True
            self.shot_active = shot_active
            self.cleaning_active = cleaning_active
            self._previous_volume_ml = volume_ml
            self._current_shot_peak_volume_ml = volume_ml if shot_active else 0
            return False

        changed = False
        if shot_active and not self.shot_active:
            self.observed_shots_total += 1
            self._current_shot_peak_volume_ml = volume_ml
            changed = True

        previous_volume = self._previous_volume_ml
        continuous_idle = (
            state.state == "idle"
            and not telemetry.water_level_alarm
            and sample_gap is not None
            and 0 <= sample_gap <= SHOT_TAIL_MAX_SAMPLE_GAP_SECONDS
            and previous_volume is not None
            and volume_ml >= previous_volume
        )
        if self._shot_tail_started_at is not None:
            tail_age = (observed_at - self._shot_tail_started_at).total_seconds()
            if (
                not continuous_idle
                or not 0 <= tail_age <= SHOT_TAIL_SECONDS
                or brew_time != self._shot_tail_brew_time_seconds
            ):
                # Close permanently on any discontinuity; a later idle sample
                # must not reopen the previous shot's attribution window.
                self._shot_tail_started_at = None

        if previous_volume is not None:
            delta = (
                volume_ml - previous_volume
                if volume_ml >= previous_volume
                else volume_ml
            )
            if delta > 0:
                self.observed_pumped_water_ml += delta
                changed = True

        if shot_active:
            if (
                self.shot_active
                and previous_volume is not None
                and (
                    volume_ml < previous_volume
                    or (
                        previous_brew_time is not None
                        and brew_time < previous_brew_time
                    )
                )
            ):
                self._current_shot_peak_volume_ml = 0
            self._current_shot_peak_volume_ml = max(
                self._current_shot_peak_volume_ml, volume_ml
            )
        elif self.shot_active:
            self.last_shot_utc = observed_at
            self.last_shot_volume_ml = self._current_shot_peak_volume_ml
            self._current_shot_peak_volume_ml = 0
            if (
                continuous_idle
                and previous_brew_time is not None
                and brew_time >= previous_brew_time
            ):
                self._shot_tail_started_at = observed_at
                self._shot_tail_brew_time_seconds = brew_time
            changed = True

        if (
            self._shot_tail_started_at is not None
            and self.last_shot_volume_ml is not None
            and volume_ml > self.last_shot_volume_ml
        ):
            # Refine only volume, retaining the first idle timestamp and count.
            # Total water already accounts for this delta above; do not add twice.
            self.last_shot_volume_ml = volume_ml
            changed = True

        if (
            self.last_shot_utc is not None
            and self.last_shot_volume_ml is not None
            and changed
            and not shot_active
            and (
                self.last_shot_utc == observed_at
                or self._shot_tail_started_at is not None
            )
        ):
            self.journal.refine_volume(
                self.last_shot_utc,
                self.last_shot_volume_ml,
                telemetry,
                observed_at,
                source,
            )

        if self.cleaning_active and not cleaning_active:
            self.last_cleaning_utc = observed_at
            changed = True

        self.shot_active = shot_active
        self.cleaning_active = cleaning_active
        self._previous_volume_ml = volume_ml
        if changed:
            self._schedule_save()
        return changed
