import json
import re
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "defaults/noctalia/config.toml"
MEDIA_CONFIG = ROOT / "defaults/noctalia/media.json"
THEME_PLUGIN = ROOT / "plugins/themes"
PROFILE_PLUGIN = ROOT / "plugins/profile"
CHEATSHEET_PLUGIN = ROOT / "plugins/cheatsheet"
MEDIA_PLUGIN = ROOT / "plugins/media"
MEDIA_FILES = (
    "plugin.toml",
    "service.luau",
    "desktop.luau",
    "player_panel.luau",
    "queue_panel.luau",
)
DEFAULT_MEDIA_API = "http://127.0.0.1:26538/api/v1"
ACTIVITY_UUIDS = ("012e885b", "db345c88")
CONNECTOR_NAMES = ("DP-1", "DP-2", "HDMI")


def test_noctalia_base_is_valid_toml():
    with CONFIG.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["bar"]["order"] == ["main"]


def test_generated_noctalia_config_starts_with_installer_marker():
    from rice.generate import generate_noctalia
    from rice.installer import NOCTALIA_GENERATED_MARKER

    assert generate_noctalia({}).startswith(NOCTALIA_GENERATED_MARKER)


def test_noctalia_base_has_no_personal_or_connector_paths():
    text = CONFIG.read_text(encoding="utf-8")
    assert "/home/" not in text
    assert "HDMI-A-1" not in text
    assert "DP-1" not in text
    assert "DP-2" not in text
    assert "rice-theme " not in text
    assert "rice-activity " not in text


def test_theme_plugin_manifest_is_valid_toml():
    with (THEME_PLUGIN / "plugin.toml").open("rb") as handle:
        data = tomllib.load(handle)
    assert data["id"] == "rice/themes"
    assert data["version"] == "1.1.0"
    assert data["license"] == "MIT"
    assert data["panel"][0]["id"] == "panel"
    assert data["panel"][0]["entry"] == "panel.luau"


def test_theme_plugin_files_exist():
    assert (THEME_PLUGIN / "panel.luau").is_file()
    assert (THEME_PLUGIN / "plugin.toml").is_file()


def test_theme_plugin_has_no_personal_paths():
    for path in THEME_PLUGIN.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert "/home/" not in text, f"personal path in {path.name}"
        assert "rice-theme " not in text, f"legacy rice-theme call in {path.name}"


def test_plugin_manifests_exist_and_parse():
    for directory, plugin_id in (
        (PROFILE_PLUGIN, "rice/profile"),
        (CHEATSHEET_PLUGIN, "rice/cheatsheet"),
    ):
        manifest = directory / "plugin.toml"
        assert manifest.is_file(), f"missing {manifest}"
        with manifest.open("rb") as handle:
            data = tomllib.load(handle)
        assert data["id"] == plugin_id
        assert data["license"] == "MIT"
        assert data["plugin_api"] == 51


def test_plugin_sources_are_path_neutral_and_role_neutral():
    for directory in (PROFILE_PLUGIN, CHEATSHEET_PLUGIN):
        files = [path for path in directory.iterdir() if path.is_file()]
        assert files, f"no files in {directory}"
        for path in files:
            text = path.read_text(encoding="utf-8")
            assert "/home/" not in text, f"personal path in {path.name}"
            for uuid in ACTIVITY_UUIDS:
                assert uuid not in text, f"hard-coded activity id in {path.name}"
            for connector in CONNECTOR_NAMES:
                assert connector not in text, f"connector name in {path.name}"


def test_profile_plugin_has_no_hardcoded_activity_uuid():
    text = (ROOT / "plugins/profile/widget.luau").read_text(encoding="utf-8")
    assert "012e885b" not in text
    assert "db345c88" not in text


def test_cheatsheet_panel_lists_generated_shortcuts_only():
    panel = (CHEATSHEET_PLUGIN / "panel.luau").read_text(encoding="utf-8")
    for key in (
        "Meta+M",
        "Meta+N",
        "Meta+Q",
        "Meta+H",
        "Meta+J",
        "Meta+1",
        "Meta+2",
        "Meta+3",
        "Meta+Left",
        "Meta+Right",
        "Meta+Return",
        "Meta+Shift+Return",
        "Ctrl+Alt+Shift+Left",
        "Ctrl+Alt+Shift+Right",
        "Ctrl+Alt+R",
        "Ctrl+Alt+H",
    ):
        assert key in panel, f"missing generated shortcut {key!r} in panel.luau"
    for stale in ("Acer", "Ctrl+Alt+7", "Ctrl+Alt+Shift+T", "Alacritty", "Kitty"):
        assert stale not in panel, f"stale label {stale!r} in panel.luau"


def test_cheatsheet_panel_width_matches_manifest():
    panel = (CHEATSHEET_PLUGIN / "panel.luau").read_text(encoding="utf-8")
    match = re.search(r"local WIDTH = (\d+)", panel)
    assert match, "WIDTH constant missing from panel.luau"
    with (CHEATSHEET_PLUGIN / "plugin.toml").open("rb") as handle:
        manifest = tomllib.load(handle)
    assert int(match.group(1)) == manifest["panel"][0]["width"]


def test_media_plugin_files_exist_and_manifest_is_valid_toml():
    for name in MEDIA_FILES:
        assert (MEDIA_PLUGIN / name).is_file(), f"missing plugins/media/{name}"
    with (MEDIA_PLUGIN / "plugin.toml").open("rb") as handle:
        data = tomllib.load(handle)
    assert data["id"] == "rice/media"
    assert data["license"] == "MIT"
    assert data["plugin_api"] == 51


def test_media_plugin_is_metadata_only_and_has_no_personal_paths():
    # Built at runtime so the privacy scan does not flag this assertion.
    personal_path = "/home/" + "dion"
    for name in MEDIA_FILES:
        text = (MEDIA_PLUGIN / name).read_text(encoding="utf-8")
        assert "/home/" not in text, f"personal path in plugins/media/{name}"
        assert personal_path not in text, f"personal path in plugins/media/{name}"


def test_media_plugin_reads_configurable_api_from_home():
    for name in ("service.luau", "desktop.luau", "player_panel.luau", "queue_panel.luau"):
        text = (MEDIA_PLUGIN / name).read_text(encoding="utf-8")
        assert 'noctalia.getenv("HOME")' in text, f"no HOME usage in {name}"
        assert "/noctalia/media.json" in text, f"no config path in {name}"
        assert "config.api_url" in text, f"no configurable api_url in {name}"


def test_media_default_config_is_valid_json_with_api_url():
    data = json.loads(MEDIA_CONFIG.read_text(encoding="utf-8"))
    assert data["api_url"] == DEFAULT_MEDIA_API
    assert "_comment" in data
    assert "optional" in data["_comment"].lower() or "opt-in" in data["_comment"].lower()
    assert "rice/media" not in CONFIG.read_text(encoding="utf-8")


def test_media_plugin_user_facing_strings_are_english():
    german_markers = (
        "Schließen",
        "Warteschlange",
        "Queue neu laden",
        "Lade Queue",
        "Queue ist leer",
        "Als Nächstes",
        "Queue nicht erreichbar",
        "Queue konnte nicht gelesen werden",
        "YouTube Music ist nicht aktiv",
    )
    for path in sorted(MEDIA_PLUGIN.glob("*.luau")):
        text = path.read_text(encoding="utf-8")
        for marker in german_markers:
            assert marker not in text, f"German UI string {marker!r} in {path.name}"
