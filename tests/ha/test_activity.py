"""Read-only activity derivation and persistence tests."""

from dataclasses import replace
from datetime import UTC, datetime

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
