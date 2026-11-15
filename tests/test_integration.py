"""End-to-end coverage for the apply pipeline.

The tests isolate every XDG directory inside ``tmp_path`` so a run can never
touch the real desktop session. They exercise the contract that the public
documentation promises: ``rice apply --dry-run`` reports every generated
artifact and writes nothing, while a real apply produces exactly that plan.
"""

import json
import tomllib
from pathlib import Path

from rice.apply import apply_config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "defaults/rice.toml"
SYSTEMD_UNITS = {
    "rice-daemon.service",
    "rice-startup.service",
    "rice-theme-boot.service",
    "rice-theme-hourly.service",
    "rice-theme-hourly.timer",
}


def _isolate_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "config", tmp_path / "data", tmp_path / "state"


def test_dry_run_lists_generated_paths(tmp_path, monkeypatch):
    config_dir, data_dir, state_dir = _isolate_xdg(tmp_path, monkeypatch)

    def unexpected(*args, **kwargs):
        raise AssertionError(f"dry-run ran a command: {args!r}")

    result = apply_config(DEFAULT_CONFIG, dry_run=True, runner=unexpected)

    paths = [str(path) for path in result.changed]
    assert any("main.js" in path for path in paths)
    assert result.skipped == []
    assert len(paths) == len(set(paths))
    assert all(str(tmp_path) in path for path in paths)
    names = {path.name for path in result.changed}
    assert {"main.js", "metadata.json", "config.toml", "runtime.json"} <= names
    assert SYSTEMD_UNITS <= names
    assert not data_dir.exists()
    assert not config_dir.exists()
    assert not state_dir.exists()


def test_apply_writes_every_planned_artifact(tmp_path, monkeypatch):
    config_dir, data_dir, state_dir = _isolate_xdg(tmp_path, monkeypatch)

    planned = apply_config(DEFAULT_CONFIG, dry_run=True)
    applied = apply_config(DEFAULT_CONFIG, runner=lambda *args, **kwargs: None)

    assert planned.changed == applied.changed
    assert all(path.is_file() for path in applied.changed)

    kwin = data_dir / "kwin/scripts/rice-placement"
    metadata = json.loads((kwin / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["KPlugin"]["Id"] == "rice-placement"
    assert metadata["X-Plasma-MainScript"] == "code/main.js"
    assert "const RULES" in (kwin / "contents/code/main.js").read_text(encoding="utf-8")

    noctalia = tomllib.loads(
        (config_dir / "noctalia/config.toml").read_text(encoding="utf-8")
    )
    assert noctalia["desktop_widgets"]["enabled"] is True

    runtime = json.loads(
        (state_dir / "rice/runtime.json").read_text(encoding="utf-8")
    )
    assert runtime["apps"]["browser"]["command"] == ["firefox"]
    assert runtime["activities"]["private"]["name"] == "Private"
    assert all((config_dir / "systemd/user" / unit).is_file() for unit in SYSTEMD_UNITS)
