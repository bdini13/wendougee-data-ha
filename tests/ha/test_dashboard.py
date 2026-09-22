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


def test_dashboard_uses_canonical_name_and_no_machine_control_entities():
    dashboard = yaml.safe_load(Path("dashboards/espresso.yaml").read_text())
    assert dashboard["title"] == "Espresso"
    assert dashboard["views"][0]["title"] == "WENDOUGEE DATA S"

    entities = set(_entities(dashboard))
    assert {
        "sensor.wendougee_data_s_observed_shots_total",
        "sensor.wendougee_data_s_observed_pumped_water_total",
        "sensor.wendougee_data_s_last_observed_backflush",
    } <= entities
    assert not any(
        entity.startswith(
            ("switch.wendougee_data", "number.wendougee_data", "button.wendougee_data")
        )
        for entity in entities
    )

    # Fixed gauge ranges become incorrect when HA converts °C/bar to °F/psi.
    assert "gauge" not in set(_card_types(dashboard))
