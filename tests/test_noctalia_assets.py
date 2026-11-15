from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "defaults/noctalia/config.toml"
THEME_PLUGIN = ROOT / "plugins/themes"


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
