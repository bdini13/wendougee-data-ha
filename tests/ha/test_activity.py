"""Read-only activity derivation and persistence tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.wendougee_data._protocol.state import OperatingState
from custom_components.wendougee_data.activity import ActivityTracker

from .test_integration import TELEMETRY

pytestmark = pytest.mark.asyncio

IDLE = OperatingState(
    raw_bits=0,
    profile_active=False,
    manual_active=False,
    cleaning_active=False,
    free_variable_active=False,
    unknown_bits=0,
)
MANUAL = replace(IDLE, raw_bits=16, manual_active=True)
CLEANING = replace(IDLE, raw_bits=32, cleaning_active=True)
PROFILE = replace(IDLE, raw_bits=2, profile_active=True)
UNKNOWN = replace(IDLE, raw_bits=64, unknown_bits=64)
AMBIGUOUS = replace(PROFILE, raw_bits=34, cleaning_active=True)


def sample(tracker, seconds, volume, state=IDLE, timer=22.4):
    """Synthetic paired observations; no private response frames or identifiers."""
    return tracker.observe(
        replace(
            TELEMETRY,
            dispensed_volume_ml=volume,
            elapsed_brew_time_seconds=timer,
            water_level_alarm=False,
        ),
        state,
        datetime(2026, 9, 26, tzinfo=UTC) + timedelta(seconds=seconds),
    )


def shot_end(tracker):
    sample(tracker, 0, 0)
    sample(tracker, 1, 64, PROFILE, 22.0)
    sample(tracker, 1.614, 65)


async def test_terminal_volume_from_reviewed_shot_sequence(hass):
    tracker = ActivityTracker(hass, "synthetic")
    shot_end(tracker)
    ended = tracker.last_shot_utc
    assert tracker.last_shot_volume_ml == 65
    sample(tracker, 2.230, 65)
    sample(tracker, 2.740, 65)
    assert sample(tracker, 3.150, 66)
    sample(tracker, 3.561, 66)
    assert tracker.last_shot_volume_ml == 66
    assert tracker.last_shot_utc == ended
    assert tracker.observed_shots_total == 1
    assert tracker.observed_pumped_water_ml == 66
    await tracker.async_save()
    restored = ActivityTracker(hass, "synthetic")
    await restored.async_load()
    assert restored.last_shot_volume_ml == 66
    assert restored.last_shot_utc == ended
    # The tail is deliberately runtime-only: reload must not attach new water.
    sample(restored, 4, 67)
    sample(restored, 4.5, 68)
    assert restored.last_shot_volume_ml == 66


@pytest.mark.parametrize(
    ("seconds", "volume", "state", "timer"),
    [
        (4, 67, IDLE, 22.4),  # gap >2 seconds
        (1.5, 67, IDLE, 22.4),  # clock moved backwards
        (2, 0, IDLE, 22.4),  # counter reset
        (2, 67, IDLE, 0),  # timer reset
        (2, 67, IDLE, 22.5),  # different timer, not latched terminal telemetry
        (2, 67, CLEANING, 22.4),
        (2, 67, UNKNOWN, 22.4),
        (2, 67, AMBIGUOUS, 22.4),
    ],
)
async def test_tail_closes_permanently_on_discontinuity(
    hass, seconds, volume, state, timer
):
    tracker = ActivityTracker(hass, "synthetic")
    shot_end(tracker)
    sample(tracker, seconds, volume, state, timer)
    assert tracker.last_shot_volume_ml == 65
    if state != AMBIGUOUS:
        sample(tracker, seconds + 0.5, 70)
        assert tracker.last_shot_volume_ml == 65


async def test_tail_has_fixed_deadline_not_sliding_window(hass):
    tracker = ActivityTracker(hass, "synthetic")
    shot_end(tracker)
    for second in (2, 3, 4, 5, 6):
        sample(tracker, second, 65)
    sample(tracker, 6.614, 66)  # exactly five seconds after first idle
    assert tracker.last_shot_volume_ml == 66
    sample(tracker, 6.615, 70)
    assert tracker.last_shot_volume_ml == 66
    assert tracker.observed_pumped_water_ml == 70


async def test_new_shot_does_not_amend_previous_shot(hass):
    tracker = ActivityTracker(hass, "synthetic")
    shot_end(tracker)
    sample(tracker, 2, 1, PROFILE, 0.1)
    assert tracker.last_shot_volume_ml == 65
    sample(tracker, 2.5, 3, PROFILE, 0.6)
    sample(tracker, 3, 4, IDLE, 0.7)
    sample(tracker, 3.5, 5, IDLE, 0.7)
    assert tracker.last_shot_volume_ml == 5
    assert tracker.observed_shots_total == 2


@pytest.mark.parametrize("state", [IDLE, CLEANING, UNKNOWN])
async def test_long_poll_gap_never_opens_terminal_window(hass, state):
    tracker = ActivityTracker(hass, "synthetic")
    sample(tracker, 0, 0)
    sample(tracker, 1, 64, PROFILE, 22.0)
    sample(tracker, 31, 100, state)
    sample(tracker, 31.5, 101)
    assert tracker.last_shot_volume_ml == 64


@pytest.mark.parametrize(
    ("state", "volume", "timer"),
    [(CLEANING, 100, 22.4), (UNKNOWN, 100, 22.4), (IDLE, 0, 22.4), (IDLE, 65, 0)],
)
async def test_discontinuous_first_idle_does_not_claim_terminal_volume(
    hass, state, volume, timer
):
    tracker = ActivityTracker(hass, "synthetic")
    sample(tracker, 0, 0)
    sample(tracker, 1, 64, PROFILE, 22.0)
    sample(tracker, 1.5, volume, state, timer)
    sample(tracker, 2, 101)
    assert tracker.last_shot_volume_ml == 64


async def test_water_alarm_closes_tail(hass):
    tracker = ActivityTracker(hass, "synthetic")
    shot_end(tracker)
    tracker.observe(
        replace(
            TELEMETRY,
            dispensed_volume_ml=66,
            elapsed_brew_time_seconds=22.4,
            water_level_alarm=True,
        ),
        IDLE,
        datetime(2026, 9, 26, tzinfo=UTC) + timedelta(seconds=2),
    )
    sample(tracker, 2.5, 67)
    assert tracker.last_shot_volume_ml == 65


async def test_tracks_only_observed_shots_water_and_cleaning(hass):
    tracker = ActivityTracker(hass, "synthetic")
    start = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)

    assert not tracker.observe(replace(TELEMETRY, dispensed_volume_ml=0), IDLE, start)
    assert tracker.observed_shots_total == 0
    assert tracker.observed_pumped_water_ml == 0

    assert tracker.observe(replace(TELEMETRY, dispensed_volume_ml=12), MANUAL, start)
    assert tracker.observed_shots_total == 1
    assert tracker.observed_pumped_water_ml == 12
    assert tracker.shot_active

    assert tracker.observe(replace(TELEMETRY, dispensed_volume_ml=36), MANUAL, start)
    assert tracker.observed_pumped_water_ml == 36

    assert tracker.observe(replace(TELEMETRY, dispensed_volume_ml=0), IDLE, start)
    assert tracker.last_shot_utc == start
    assert tracker.last_shot_volume_ml == 36
    assert not tracker.shot_active

    assert tracker.observe(TELEMETRY, CLEANING, start)
    assert tracker.cleaning_active
    assert tracker.observe(TELEMETRY, IDLE, start)
    assert tracker.last_cleaning_utc == start
    assert not tracker.cleaning_active


async def test_restores_durable_totals_without_fabricating_transitions(hass):
    tracker = ActivityTracker(hass, "synthetic")
    tracker.observed_shots_total = 7
    tracker.observed_pumped_water_ml = 245.0
    tracker.last_shot_utc = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    tracker.last_shot_volume_ml = 34
    tracker.last_cleaning_utc = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    await tracker.async_save()

    restored = ActivityTracker(hass, "synthetic")
    await restored.async_load()

    assert restored.observed_shots_total == 7
    assert restored.observed_pumped_water_ml == 245.0
    assert restored.last_shot_volume_ml == 34
    assert restored.last_shot_utc == tracker.last_shot_utc
    assert restored.last_cleaning_utc == tracker.last_cleaning_utc
    assert not restored.observe(TELEMETRY, MANUAL, datetime.now(UTC))
    assert restored.observed_shots_total == 7
