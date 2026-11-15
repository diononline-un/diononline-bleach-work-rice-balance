import tomllib
from pathlib import Path

import pytest

from rice.layouts import choose_layout, default_placements, layout_config
from rice.outputs import Output

LAYOUTS = Path(__file__).resolve().parents[1] / "defaults" / "layouts"

OUTPUTS = {
    "triple": [
        Output("main", "DP-1", 5120, 1440, 0, 0, True),
        Output("side", "HDMI-A-1", 2560, 1440, 5120, 0, False),
        Output("portrait", "DP-2", 1080, 1920, 7680, 0, False),
    ],
    "single-split": [Output("main", "DP-1", 2560, 1440, 0, 0, True)],
    "ultrawide": [Output("main", "DP-1", 5120, 1440, 0, 0, True)],
}


def test_single_wide_chooses_ultrawide():
    assert choose_layout([Output("main", "DP-1", 5120, 1440, 0, 0, True)]) == "ultrawide"


def test_ultrawide_has_two_center_app_zones():
    outputs = [Output("main", "DP-1", 5120, 1440, 0, 0, True)]
    config = layout_config("ultrawide", outputs)
    app_zones = [zone["id"] for zone in config["zone"] if zone["kind"] == "app"]
    assert "center-left" in app_zones
    assert "center-right" in app_zones


def test_triple_uses_non_primary_outputs_regardless_of_order():
    # KScreen may list the primary at any index; secondaries are chosen by
    # identity, not by position.
    outputs = [
        Output("output-1", "HDMI-A-1", 2560, 1440, 0, 0, False),
        Output("main", "DP-1", 5120, 1440, 2560, 0, True),
        Output("output-3", "DP-2", 1080, 1920, 7680, 0, False),
    ]
    zones = {
        zone["id"]: zone["output"] for zone in layout_config("triple", outputs)["zone"]
    }
    assert zones["main-left"] == zones["main-right"] == "main"
    assert zones["side-left"] == zones["side-right"] == "output-1"
    assert zones["portrait-full"] == "output-3"
    assert set(zones.values()) == {"main", "output-1", "output-3"}


def test_triple_requires_two_non_primary_outputs():
    outputs = [
        Output("main", "DP-1", 5120, 1440, 0, 0, True),
        Output("output-2", "HDMI-A-1", 2560, 1440, 5120, 0, False),
    ]
    with pytest.raises(ValueError, match="non-primary outputs"):
        layout_config("triple", outputs)


@pytest.mark.parametrize("preset", ["triple", "single-split", "ultrawide"])
def test_default_placements_reference_preset_zones(preset):
    zone_ids = {zone["id"] for zone in layout_config(preset, OUTPUTS[preset])["zone"]}
    rules = default_placements(
        preset,
        {
            "private-browser": {"activities": ["private"]},
            "work-browser": {"activities": ["work"]},
            "terminal": {"activities": ["private", "work"]},
            "gpu-recorder": {"activities": ["private", "work"]},
            "discord": {"activities": ["private"]},
            "unknown-app": {},
        },
    )
    assert rules
    assert all(rule["zone"] in zone_ids for rule in rules)
    assert all(rule["app"] != "unknown-app" for rule in rules)


@pytest.mark.parametrize("preset", ["triple", "single-split", "ultrawide"])
def test_preset_files_match_python_zones(preset):
    with (LAYOUTS / f"{preset}.toml").open("rb") as handle:
        data = tomllib.load(handle)
    fields = ("id", "kind", "x", "y", "w", "h", "gap_px")
    expected = [
        {field: zone[field] for field in fields}
        for zone in layout_config(preset, OUTPUTS[preset])["zone"]
    ]
    actual = [{field: zone[field] for field in fields} for zone in data["zone"]]
    assert actual == expected
