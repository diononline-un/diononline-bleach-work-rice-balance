from copy import deepcopy

import pytest

from rice.generate import generate_kwin, kwin_rules

CONFIG = {
    "output": [{"id": "main", "connector": "DP-1", "primary": True, "x": 0, "y": 0, "width": 5120, "height": 1440}],
    "zone": [{"id": "center-left", "output": "main", "kind": "app",
              "x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8}],
    "app": [{"id": "browser", "command": ["firefox"], "wm_class": "firefox"}],
    "placement": [{"app": "browser", "activity": "private", "zone": "center-left", "mode": "normal"}],
    "activities": {"private": {"name": "Private", "kde_id": "private-uuid"},
                   "work": {"name": "Work", "kde_id": "work-uuid"}},
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
