import tomllib
from copy import deepcopy
from pathlib import Path

import pytest

from rice.generate import (
    _widget_anchor,
    generate_kwin,
    generate_noctalia,
    generate_runtime,
    generate_systemd,
    kwin_rules,
)

ROOT = Path(__file__).resolve().parents[1]

CONFIG = {
    "output": [{"id": "main", "connector": "DP-1", "primary": True, "x": 0, "y": 0, "width": 5120, "height": 1440}],
    "zone": [{"id": "center-left", "output": "main", "kind": "app",
              "x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8}],
    "app": [{"id": "browser", "command": ["firefox"], "wm_class": "firefox"}],
    "placement": [{"app": "browser", "activity": "private", "zone": "center-left", "mode": "normal"}],
    "activities": {"private": {"name": "Private", "kde_id": "private-uuid"},
                   "work": {"name": "Work", "kde_id": "work-uuid"}},
    "startup": {"always": [], "private": ["browser"]},
    "desktop_widget": [{"id": "clock", "plugin": "clock", "zone": "center-left", "scale": 1.0}],
}


def test_rules_resolve_zone_and_activity():
    rules = kwin_rules(CONFIG)
    assert rules[0]["wm_class"] == "firefox"
    assert rules[0]["output"] == "DP-1"
    assert rules[0]["activity"] == "private-uuid"
    assert rules[0]["zone"]["w"] == 0.5


def test_generated_js_contains_rules():
    js = generate_kwin(CONFIG)
    assert "const RULES =" in js
    assert "firefox" in js


def test_rules_use_lowercase_class_and_title():
    config = deepcopy(CONFIG)
    config["app"][0]["wm_class"] = "Firefox"
    config["placement"][0]["match_title"] = "Mozilla Firefox"
    rule = kwin_rules(config)[0]
    assert rule["wm_class"] == "firefox"
    assert rule["match_title"] == "mozilla firefox"


def test_missing_wm_class_falls_back_to_title_match():
    config = deepcopy(CONFIG)
    config["app"] = [{"id": "claude", "command": ["claude"]}]
    config["placement"] = [{"app": "claude", "activity": "private", "zone": "center-left",
                            "mode": "normal", "match_title": "Claude Code"}]
    rule = kwin_rules(config)[0]
    assert rule["wm_class"] == ""
    assert rule["match_title"] == "claude code"


def test_rules_without_class_or_title_are_never_catch_all():
    config = deepcopy(CONFIG)
    config["app"] = [{"id": "bare", "command": ["bare"]}]
    config["placement"] = [{"app": "bare", "activity": "private", "zone": "center-left",
                            "mode": "normal"}]
    js = generate_kwin(config)
    assert '"wm_class": ""' in js
    assert '"match_title": ""' in js
    # The script must skip rules that match neither class nor title.
    assert "if (!rule.wm_class && !rule.match_title) continue;" in js


def test_higher_priority_rule_comes_first():
    config = deepcopy(CONFIG)
    config["zone"].append({"id": "center-right", "output": "main", "kind": "app",
                           "x": 0.5, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8})
    config["placement"] = [
        {"app": "browser", "activity": "private", "zone": "center-left", "mode": "normal"},
        {"app": "browser", "activity": "private", "zone": "center-right",
         "mode": "maximized", "priority": 10},
    ]
    rules = kwin_rules(config)
    assert [rule["zone"]["x"] for rule in rules] == [0.5, 0.0]


def test_template_reports_fullscreen_to_daemon():
    js = generate_kwin(CONFIG)
    assert "org.rice.Rice" in js
    assert "SetFullscreen" in js


def test_generated_js_keeps_single_placeholder_replacement():
    js = generate_kwin(CONFIG)
    assert "__RULES__" not in js
    assert js.startswith("const RULES = [")


@pytest.mark.parametrize("mode", ["normal", "maximized", "fullscreen"])
def test_mode_is_passed_through(mode):
    config = deepcopy(CONFIG)
    config["placement"][0]["mode"] = mode
    assert kwin_rules(config)[0]["mode"] == mode


def test_noctalia_output_is_valid_toml():
    data = tomllib.loads(generate_noctalia(CONFIG))
    assert "desktop_widgets" in data


def test_noctalia_widget_uses_zone_center_in_output_pixels():
    data = tomllib.loads(generate_noctalia(CONFIG))
    widgets = data["desktop_widgets"]["widget"]
    assert data["desktop_widgets"]["widget_order"] == ["rice_0"]
    assert widgets["rice_0"] == {
        "type": "clock",
        "output": "DP-1",
        "cx": 1280.0,
        "cy": 720.0,
        "scale": 1.0,
    }


def test_noctalia_without_widgets_is_still_valid_toml():
    config = deepcopy(CONFIG)
    config["desktop_widget"] = []
    data = tomllib.loads(generate_noctalia(config))
    assert data["desktop_widgets"]["widget_order"] == []
    assert data["desktop_widgets"]["widget"] == {}


def test_widget_anchor_defaults_missing_geometry_fields():
    config = {
        "output": [{"id": "main", "connector": "DP-1", "width": 1000, "height": 500}],
        "zone": [{"id": "bare", "output": "main"}],
    }
    anchor = _widget_anchor(config, {"plugin": "clock", "zone": "bare"})
    assert (anchor["cx"], anchor["cy"]) == (0.0, 0.0)


def test_runtime_contains_startup_and_zones():
    data = generate_runtime(CONFIG)
    assert data["startup"]["private"] == ["browser"]
    assert data["zones"]["center-left"]["w"] == 0.5
    assert data["apps"]["browser"]["command"] == ["firefox"]


def test_systemd_units_have_user_exec():
    units = generate_systemd(CONFIG, ROOT)
    content = "\n".join(units.values())
    assert "rice startup" in content
    assert "rice daemon" in content


def test_systemd_units_are_path_neutral_and_cover_runtime():
    units = generate_systemd(CONFIG, ROOT)
    content = "\n".join(units.values())
    assert "/home/" not in content
    assert "%h/.local/bin/rice" in content
    assert "rice theme boot" in content
    assert "rice theme hourly" in content


def test_hourly_timer_triggers_hourly_service():
    units = generate_systemd(CONFIG, ROOT)
    timer = units[Path("rice-theme-hourly.timer")]
    assert "OnCalendar=hourly" in timer
    assert "Unit=rice-theme-hourly.service" in timer
    assert "@RICE_COMMAND@" not in "".join(units.values())
