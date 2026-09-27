"""Read-only notification templates must reject stale and unrelated events."""

import pytest
from homeassistant.helpers.template import Template

from scripts.boiler_notifications import automations


@pytest.mark.asyncio
async def test_ready_gates_and_daily_dedup(hass):
    config = automations(["notify.mobile_app_example"])[0]
    template = Template(config["conditions"][0]["value_template"], hass)
    hass.states.async_set("input_boolean.espresso_brew_schedule_enabled", "on")
    hass.states.async_set("binary_sensor.wendougee_data_brew_heating_enabled", "on")
    hass.states.async_set(
        "sensor.wendougee_data_brew_temperature", "198", {"unit_of_measurement": "°F"}
    )
    hass.states.async_set(
        "sensor.wendougee_data_brew_target", "197.6", {"unit_of_measurement": "°F"}
    )
    from homeassistant.util import dt as dt_util

    hass.states.async_set(
        "sensor.wendougee_data_s_communication_health",
        "healthy",
        {"last_successful_poll": dt_util.utcnow().isoformat()},
    )
    hass.states.async_set("input_text.espresso_brew_ready_notified", "none")
    assert template.async_render() is True
    hass.states.async_set(
        "input_text.espresso_brew_ready_notified", dt_util.now().date().isoformat()
    )
    assert template.async_render() is False
    hass.states.async_set("input_text.espresso_brew_ready_notified", "none")
    hass.states.async_set("input_boolean.espresso_brew_schedule_enabled", "off")
    assert template.async_render() is False
    hass.states.async_set("input_boolean.espresso_brew_schedule_enabled", "on")
    hass.states.async_set("sensor.wendougee_data_s_communication_health", "read_failed")
    assert template.async_render() is False


def test_notifications_have_no_hardware_actions():
    configs = automations(["notify.mobile_app_one", "notify.mobile_app_two"])
    assert len(configs) == 4
    for config in configs:
        assert config["mode"] == "single"
        assert [a["action"] for a in config["actions"]] == [
            "input_text.set_value",
            "notify.mobile_app_one",
            "notify.mobile_app_two",
        ]
        assert all(a.get("continue_on_error") for a in config["actions"][1:])


def test_friendly_copy_identifies_each_boiler():
    configs = automations(["notify.mobile_app_example"])
    messages = [c["actions"][1]["data"]["message"] for c in configs]
    assert "☕ Espresso time!" in messages[0]
    assert "Brew boiler" in messages[0]
    assert "💨 Ready to steam!" in messages[2]
    assert "Steam boiler" in messages[2]
    for index, boiler in ((1, "Brew"), (3, "Steam")):
        assert f"{boiler} boiler" in messages[index]
        assert "scheduled shutdown verified" in messages[index]
        assert "still be hot" in messages[index]


@pytest.mark.asyncio
async def test_off_requires_new_verified_scheduled_result(hass):
    from homeassistant.core import State
    from homeassistant.util import dt as dt_util

    config = automations(["notify.mobile_app_example"])[1]
    template = Template(config["conditions"][0]["value_template"], hass)
    hass.states.async_set("input_boolean.espresso_brew_schedule_enabled", "on")
    hass.states.async_set("input_text.espresso_brew_off_notified", "none")
    stamp = dt_util.utcnow().isoformat()
    old = State("sensor.test", "executing", {"last_verified_at": None})
    new = State(
        "sensor.test",
        "armed",
        {"last_verified_at": stamp, "last_result": "verified_off"},
    )
    assert (
        template.async_render({"trigger": {"from_state": old, "to_state": new}}) is True
    )
    assert (
        template.async_render({"trigger": {"from_state": None, "to_state": new}})
        is False
    )
    assert (
        template.async_render({"trigger": {"from_state": new, "to_state": new}})
        is False
    )
    hass.states.async_set("input_text.espresso_brew_off_notified", stamp)
    assert (
        template.async_render({"trigger": {"from_state": old, "to_state": new}})
        is False
    )
