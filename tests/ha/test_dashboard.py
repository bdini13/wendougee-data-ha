"""Dashboard structure and safety-boundary tests."""

from pathlib import Path

import yaml


def _entities(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "entity" and isinstance(child, str):
                yield child
            yield from _entities(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, str) and "." in child:
                yield child
            else:
                yield from _entities(child)


def _card_types(value):
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value["type"]
        for child in value.values():
            yield from _card_types(child)
    elif isinstance(value, list):
        for child in value:
            yield from _card_types(child)


def test_dashboard_exposes_boilers_but_not_unverified_paddle_start():
    dashboard = yaml.safe_load(Path("dashboards/espresso.yaml").read_text())
    assert dashboard["title"] == "Espresso"
    assert dashboard["views"][0]["title"] == "WENDOUGEE DATA S"

    entities = set(_entities(dashboard))
    assert {
        "sensor.wendougee_data_s_observed_shots_total",
        "sensor.wendougee_data_s_observed_pumped_water_total",
        "sensor.wendougee_data_s_last_observed_backflush",
    } <= entities
    assert {
        entity
        for entity in entities
        if entity.startswith(
            ("switch.wendougee_data", "number.wendougee_data", "button.wendougee_data")
        )
    } == {
        "switch.wendougee_data_s_steam_boiler",
        "switch.wendougee_data_s_brew_boiler",
        "button.wendougee_data_s_start_cleaning",
    }
    cards = dashboard["views"][0]["sections"][1]["cards"]
    assert any("Paddle-bound shot" in c.get("content", "") for c in cards)
    maintenance = dashboard["views"][0]["sections"][-1]["cards"]
    cleaning = next(
        c
        for c in maintenance
        if c.get("entity") == "button.wendougee_data_s_start_cleaning"
    )
    assert cleaning["tap_action"]["confirmation"]["text"]
    assert cleaning["tap_action"]["perform_action"] == "button.press"

    # Fixed gauge ranges become incorrect when HA converts °C/bar to °F/psi.
    assert "gauge" not in set(_card_types(dashboard))
