from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "defaults/noctalia/config.toml"


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
