from pathlib import Path

import pytest

from rice.apps import app_commands, load_catalog, resolve_choices

CATALOG = {
    "work_browser": {
        "chrome": {"package": "google-chrome", "command": ["google-chrome-stable"], "wm_class": "google-chrome"},
        "firefox": {"package": "firefox", "command": ["firefox"], "wm_class": "firefox"},
    },
    "private_browser": {
        "brave": {"package": "brave-bin", "command": ["brave"], "wm_class": "brave-browser"},
        "chromium": {"package": "chromium", "command": ["chromium"], "wm_class": "chromium"},
    },
    "toggles": {
        "youtube_music": {"package": "youtube-music-bin", "command": ["youtube-music"], "wm_class": "com.github.th-ch.youtube-music"},
    },
}

DEFAULTS = Path(__file__).resolve().parents[1] / "defaults" / "apps.toml"

REQUIRED_APP_IDS = (
    "work-browser",
    "private-browser",
    "claude",
    "terminal",
    "youtube-music",
    "steam",
    "discord",
    "opencode",
    "gpu-recorder",
)


def test_resolve_choices_selects_requested_variants():
    apps = resolve_choices(CATALOG, {"work_browser": "firefox", "private_browser": "chromium", "youtube_music": True})
    assert apps["work-browser"]["command"] == ["firefox"]
    assert apps["private-browser"]["command"] == ["chromium"]
    assert "youtube-music" in apps


def test_resolve_choices_rejects_unknown_variant():
    with pytest.raises(ValueError):
        resolve_choices(CATALOG, {"work_browser": "netscape", "private_browser": "chromium"})


def test_resolve_choices_leaves_disabled_toggles_out():
    apps = resolve_choices(CATALOG, {"work_browser": "chrome", "private_browser": "brave"})
    assert set(apps) == {"work-browser", "private-browser"}


def test_app_commands_maps_app_ids_to_argv():
    apps = resolve_choices(CATALOG, {"work_browser": "firefox", "private_browser": "brave"})
    assert app_commands(apps) == {"work-browser": ["firefox"], "private-browser": ["brave"]}


def test_shipped_catalog_resolves_every_slot_and_toggle():
    catalog = load_catalog(DEFAULTS)
    assert {"work_browser", "private_browser", "claude", "terminal", "toggles"} <= set(catalog)
    choices = {
        slot: next(iter(variants))
        for slot, variants in catalog.items()
        if slot != "toggles"
    }
    choices.update({app_id: True for app_id in catalog["toggles"]})
    apps = resolve_choices(catalog, choices)
    for app_id in REQUIRED_APP_IDS:
        assert app_id in apps
    for entry in apps.values():
        assert entry["package"]
        assert entry["command"] and all(isinstance(part, str) and part for part in entry["command"])
        assert entry["activities"]
        assert set(entry["activities"]) <= {"private", "work"}


def test_shipped_catalog_stays_public_and_generic():
    text = DEFAULTS.read_text(encoding="utf-8").lower()
    for marker in ("dsh", "tailscale", "vps", "localhost", "192.168.", "http://", "https://", "/home/"):
        assert marker not in text
