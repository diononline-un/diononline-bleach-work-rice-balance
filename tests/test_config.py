from copy import deepcopy
from pathlib import Path

import pytest

from rice.config import load_config, save_config, validate_config

VALID = {
    "meta": {"schema_version": 1},
    "output": [{"id": "main", "role": "main", "connector": "DP-1", "primary": True}],
    "zone": [
        {"id": "left", "output": "main", "kind": "app", "x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8},
        {"id": "right", "output": "main", "kind": "app", "x": 0.5, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8},
    ],
    "app": [{"id": "browser", "name": "Browser", "command": ["firefox"], "wm_class": "firefox"}],
    "placement": [{"app": "browser", "activity": "private", "zone": "left", "mode": "normal"}],
    "activities": {"private": {"name": "Private", "kde_id": ""}, "work": {"name": "Work", "kde_id": ""}},
    "startup": {"always": [], "private": ["browser"]},
    "autostart": {"private": {"apps": []}, "work": {"apps": []}},
    "desktop_widget": [],
}


def test_validate_accepts_valid_config():
    assert validate_config(VALID) == []


@pytest.mark.parametrize("field", ["left", "right"])
def test_validate_rejects_zone_outside_bounds(field):
    config = deepcopy(VALID)
    config["zone"][0 if field == "left" else 1]["w"] = 1.2
    errors = validate_config(config)
    assert any("outside" in error for error in errors)


def test_validate_rejects_unknown_zone_reference():
    config = deepcopy(VALID)
    config["placement"][0]["zone"] = "missing"
    errors = validate_config(config)
    assert any("unknown zone" in error for error in errors)


def test_save_and_load_round_trip(tmp_path: Path):
    path = tmp_path / "rice.toml"
    save_config(path, VALID)
    assert load_config(path) == VALID
