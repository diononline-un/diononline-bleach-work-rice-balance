from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "defaults/noctalia/config.toml"
THEME_PLUGIN = ROOT / "plugins/themes"
PROFILE_PLUGIN = ROOT / "plugins/profile"
CHEATSHEET_PLUGIN = ROOT / "plugins/cheatsheet"
ACTIVITY_UUIDS = ("012e885b", "db345c88")
CONNECTOR_NAMES = ("DP-1", "DP-2", "HDMI")


def test_noctalia_base_is_valid_toml():
    with CONFIG.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["bar"]["order"] == ["main"]


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
