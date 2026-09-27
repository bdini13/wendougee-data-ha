"""Observability uses cached observations only; never hardware commands."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from custom_components.wendougee_data.activity import ActivityTracker
from custom_components.wendougee_data.sensor import async_setup_entry

from .test_activity import IDLE, PROFILE, sample
from .test_integration import TELEMETRY
from .test_schedules import MORNING, configured

pytestmark = pytest.mark.asyncio


async def test_schedule_health_survives_telemetry_failure_and_edits(hass):
    c = await configured(hass)
    c.entry.runtime_data = c
    await c.schedules.async_setup()
    sensors = []
    await async_setup_entry(hass, c.entry, lambda items: sensors.extend(items))
    health = next(s for s in sensors if s.entity_description.key == "brew_schedule")
    c.last_update_success = False
    with patch(
        "custom_components.wendougee_data.schedules.dt_util.now",
        return_value=MORNING - timedelta(minutes=1),
    ):
        assert health.available
        assert health.native_value == "armed"
        assert health.extra_state_attributes["next_action"] == "on"
        assert health.extra_state_attributes["next_action_at"].startswith(
            "2026-09-27T06:30"
        )
    c.schedules.pending["brew"] = True
    assert health.native_value == "check_machine"
    assert health.extra_state_attributes["next_action_at"] is None
    await c.schedules.async_shutdown()


async def test_history_retains_observations_not_inferred_final_yield(hass):
    t = ActivityTracker(hass, "journal")
    sample(t, 0, 0)
    sample(t, 1, 2, PROFILE, 0.5)
    sample(t, 1.5, 4, PROFILE, 1)
    sample(t, 2, 5, IDLE, 1.2)
    sample(t, 2.5, 6, IDLE, 1.2)
    record = t.journal.records[-1]
    assert record["pumped_ml"] == 6
    assert record["final_yield_g"] is None
    assert record["source"] == "poll"
    assert not t.journal.latest_curve
    await t.async_save()
    restored = ActivityTracker(hass, "journal")
    await restored.async_load()
    assert restored.journal.records == t.journal.records


async def test_capture_curve_is_bounded_and_drops_stale_first_active_sample(hass):
    t = ActivityTracker(hass, "curve")
    start = datetime(2026, 9, 27, tzinfo=UTC)
    for i, (state, volume, timer) in enumerate(
        [
            (IDLE, 66, 30),
            (PROFILE, 66, 30),
            (PROFILE, 0, 0.4),
            (PROFILE, 10, 1),
            (IDLE, 12, 1.2),
            (IDLE, 13, 1.2),
        ]
    ):
        t.observe(
            replace(
                TELEMETRY,
                dispensed_volume_ml=volume,
                elapsed_brew_time_seconds=timer,
                water_level_alarm=False,
                scale_weight_grams=7.5,
            ),
            state,
            start + timedelta(seconds=i / 2),
            source="capture",
        )
    assert t.last_shot_volume_ml == 13
    assert t.journal.records[-1]["pumped_ml"] == 13
    assert t.journal.records[-1]["source"] == "capture"
    assert max(p[2] for p in t.journal.latest_curve) == 13
    assert all(len(p) == 4 for p in t.journal.latest_curve)
    from custom_components.wendougee_data.shot_chart import render_chart

    svg = render_chart(t.journal.latest_curve).decode()
    assert "Pressure (bar)" in svg
    assert "Scale reading (g)" in svg
    assert "polyline" in svg
    assert "6553" not in svg


async def test_history_limit_and_legacy_restore(hass):
    t = ActivityTracker(hass, "bounded")
    for i in range(40):
        sample(t, i * 3, 0)
        sample(t, i * 3 + 1, 1, PROFILE, 0.1)
        sample(t, i * 3 + 2, 2, IDLE, 0.2)
    assert len(t.journal.records) == 30
    assert t.observed_shots_total == 40


async def test_schedule_verified_result_restores(hass):
    c = await configured(hass)
    c.schedules.last_result["brew"] = "verified_off"
    c.schedules.last_verified["brew"] = MORNING.isoformat()
    await c.schedules._save(dict(c.schedules.pending))
    other = await configured(hass)
    # Use the same identity/store, without changing either machine state.
    other.schedules.store = c.schedules.store
    await other.schedules.async_load()
    assert other.schedules.last_result["brew"] == "verified_off"
    assert other.schedules.last_verified["brew"] == MORNING.isoformat()


async def test_chart_served_through_native_image_platform(hass, hass_client):
    from .test_integration import BASELINE_FRAMES, entry

    configured_entry = entry()
    configured_entry.add_to_hass(hass)
    with patch(
        "custom_components.wendougee_data.coordinator.read_baseline",
        return_value=BASELINE_FRAMES,
    ) as read:
        assert await hass.config_entries.async_setup(configured_entry.entry_id)
        await hass.async_block_till_done()
        state = next(
            s
            for s in hass.states.async_all("image")
            if s.entity_id.endswith("latest_captured_shot")
        )
        client = await hass_client()
        response = await client.get(state.attributes["entity_picture"])
        assert response.status == 200
        assert response.content_type == "image/svg+xml"
        assert "No detailed captured shot" in await response.text()
        assert read.await_count == 1  # Image access cannot cause a BLE read/write.
        await hass.config_entries.async_unload(configured_entry.entry_id)


async def test_new_shot_and_late_water_do_not_extend_previous_curve(hass):
    t = ActivityTracker(hass, "isolation")
    start = datetime(2026, 9, 27, tzinfo=UTC)

    def observe(i, state, volume):
        t.observe(
            replace(
                TELEMETRY,
                dispensed_volume_ml=volume,
                elapsed_brew_time_seconds=1,
                water_level_alarm=False,
            ),
            state,
            start + timedelta(seconds=i),
            source="capture",
        )

    observe(0, IDLE, 0)
    observe(0.5, PROFILE, 2)
    observe(1, IDLE, 3)
    original = list(t.journal.latest_curve)
    observe(10, IDLE, 8)
    observe(10.5, PROFILE, 10)
    assert t.journal.latest_curve == original
    assert t.journal.records[-1]["pumped_ml"] == 3


async def test_ambiguous_end_is_not_a_completed_journal_entry(hass):
    from .test_activity import UNKNOWN

    t = ActivityTracker(hass, "ambiguous")
    sample(t, 0, 0)
    sample(t, 1, 1, PROFILE)
    sample(t, 2, 2, UNKNOWN)
    sample(t, 3, 3, IDLE)
    assert not t.journal.records


async def test_notification_blueprint_validates_without_machine_actions(hass):
    from homeassistant.components.automation.config import (
        AUTOMATION_BLUEPRINT_SCHEMA,
        async_validate_config_item,
    )
    from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
    from homeassistant.util.yaml import load_yaml

    data = await hass.async_add_executor_job(
        load_yaml, "blueprints/automation/wendougee_data/schedule_failure.yaml"
    )
    blueprint = Blueprint(data, schema=AUTOMATION_BLUEPRINT_SCHEMA)
    inputs = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "synthetic.yaml",
                "input": {
                    "schedule_health": "sensor.synthetic_schedule",
                    "notification": [
                        {
                            "action": "persistent_notification.create",
                            "data": {"message": "Check the machine"},
                        }
                    ],
                },
            }
        },
    )
    inputs.validate()
    result = await async_validate_config_item(
        hass, "automation", inputs.async_substitute()
    )
    assert result
    assert "wendougee_data.start" not in str(result)


async def test_next_edge_skips_attempted_date_and_spring_gap(hass):
    from zoneinfo import ZoneInfo

    c = await configured(hass)
    await c.schedules.async_setup()
    c.schedules.last_attempts["brew_on"] = MORNING.date().isoformat()
    with patch(
        "custom_components.wendougee_data.schedules.dt_util.now",
        return_value=MORNING - timedelta(minutes=1),
    ):
        action, at = c.schedules.next_edge("brew")
        assert action == "off"
        assert at.startswith("2026-09-27T09:00")
    hass.states.async_set("input_datetime.espresso_brew_on_time", "02:30:00")
    with patch(
        "custom_components.wendougee_data.schedules.dt_util.now",
        return_value=datetime(2027, 3, 14, 1, tzinfo=ZoneInfo("America/New_York")),
    ):
        action, at = c.schedules.next_edge("brew")
        assert action == "off"  # No 02:30 local time on spring-forward day.
        assert at.startswith("2027-03-14T09:00")
    await c.schedules.async_shutdown()


async def test_journal_rejects_malformed_restored_metadata():
    from custom_components.wendougee_data.shot_journal import ShotJournal

    journal = ShotJournal()
    journal.restore(
        {
            "records": [{"ended_at": "bad", "private_raw": "secret"}],
            "latest_curve": [[0, 1, 2, float("nan")]],
            "curve_updated_at": "bad",
        }
    )
    assert not journal.records
    assert not journal.latest_curve
    assert journal.curve_updated_at is None


async def test_successful_schedule_never_publishes_false_failure(hass):
    from custom_components.wendougee_data._protocol.state import decode_configuration
    from tests.test_reads import register_response

    from .test_integration import CONFIGURATION_VALUES

    c = await configured(hass)
    await c.schedules.async_setup()
    states = []
    cancel = c.async_add_listener(lambda: states.append(c.schedules.status("brew")))
    words = list(CONFIGURATION_VALUES)
    words[7] = 0
    with (
        patch(
            "custom_components.wendougee_data.schedules.dt_util.now",
            return_value=MORNING,
        ),
        patch(
            "custom_components.wendougee_data.schedules.execute_boiler",
            return_value=decode_configuration(register_response(words)),
        ),
    ):
        await c.schedules.async_run("brew", True)
    cancel()
    await c.schedules.async_shutdown()
    assert "check_machine" not in states
    assert "paused" not in states
    assert "executing" in states
