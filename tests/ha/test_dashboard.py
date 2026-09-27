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


def test_dashboard_has_native_observability_and_no_stale_schedule_claim():
    text = Path("dashboards/espresso.yaml").read_text()
    dashboard = yaml.safe_load(text)
    assert {"shots", "trends", "evidence"} <= {
        v.get("path") for v in dashboard["views"]
    }
    assert "Schedule helpers remain inactive" not in text
    assert (
        "Shot-load performance and physical units still need attended comparison"
        not in text
    )
    assert "sensor.wendougee_data_s_brew_schedule_health" in text
    assert "sensor.wendougee_data_s_steam_schedule_health" in text
    assert "image.wendougee_data_s_latest_captured_shot" in text
    assert "trend-graph" in set(_card_types(dashboard))
    assert "energy-date-selection" in set(_card_types(dashboard))
    assert not any(t.startswith("custom:") for t in _card_types(dashboard))
    assert "final_yield_g" not in text  # No unvalidated yield presented as fact.


def test_boiler_power_and_schedule_share_one_card_without_bulk_toggle():
    dashboard = yaml.safe_load(Path("dashboards/espresso.yaml").read_text())
    cards = [
        card
        for section in dashboard["views"][0]["sections"]
        for card in section["cards"]
    ]
    for boiler in ("brew", "steam"):
        switch = f"switch.wendougee_data_s_{boiler}_boiler"
        matches = [card for card in cards if switch in set(_entities(card))]
        assert len(matches) == 1
        card = matches[0]
        assert card["type"] == "entities"
        assert card["show_header_toggle"] is False
        assert {
            switch,
            f"input_boolean.espresso_{boiler}_schedule_enabled",
            f"input_datetime.espresso_{boiler}_on_time",
            f"input_datetime.espresso_{boiler}_off_time",
        } <= set(_entities(card))
        assert card["entities"][0]["name"] == "Boiler power · manual"
        assert [r["entity"] for r in card["entities"][1:3]] == [
            f"sensor.wendougee_data_{boiler}_target",
            f"sensor.wendougee_data_{boiler}_temperature",
        ]
    top = dashboard["views"][0]["sections"][0]["cards"]
    assert top[0]["type"] == "picture"
    assert top[1]["entities"][0]["entity"].endswith("brew_boiler")
    assert top[2]["entities"][0]["entity"].endswith("steam_boiler")


def test_statistics_date_collection_uses_frontend_required_prefix():
    dashboard = yaml.safe_load(Path("dashboards/espresso.yaml").read_text())
    trends = next(v for v in dashboard["views"] if v["path"] == "trends")
    linked = [
        card
        for section in trends["sections"]
        for card in section["cards"]
        if "collection_key" in card
    ]
    assert len(linked) == 3
    keys = {card["collection_key"] for card in linked}
    assert len(keys) == 1
    assert next(iter(keys)).startswith("energy_")
