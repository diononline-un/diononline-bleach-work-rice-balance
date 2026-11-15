import json
from pathlib import Path

import pytest

from rice.apply import apply_config

ROOT = Path(__file__).resolve().parents[1]


def _config(tmp_path, monkeypatch):
    config = tmp_path / "rice.toml"
    config.write_text((ROOT / "defaults/rice.toml").read_text())
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local/state"))
    return config, home


def _noop(*args, **kwargs):
    return None


def test_apply_writes_generated_files_and_backs_up(tmp_path, monkeypatch):
    config = tmp_path / "rice.toml"
    config.write_text((Path("defaults/rice.toml")).read_text())
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local/state"))
    result = apply_config(config, runner=lambda *args, **kwargs: None)
    assert any("main.js" in str(path) for path in result.changed)
    assert (home / ".config/noctalia/config.toml").exists()


def test_apply_writes_kwin_metadata_runtime_and_units(tmp_path, monkeypatch):
    config, home = _config(tmp_path, monkeypatch)

    result = apply_config(config, runner=_noop)

    kwin = home / ".local/share/kwin/scripts/rice-placement"
    metadata = json.loads((kwin / "metadata.json").read_text())
    assert metadata["KPlugin"]["Id"] == "rice-placement"
    assert metadata["X-Plasma-API"] == "javascript"
    assert metadata["X-Plasma-MainScript"] == "code/main.js"
    assert (kwin / "contents/code/main.js").is_file()

    runtime = json.loads((home / ".local/state/rice/runtime.json").read_text())
    assert runtime["apps"]["browser"]["command"] == ["firefox"]

    unit = home / ".config/systemd/user/rice-daemon.service"
    assert "rice daemon" in unit.read_text()
    assert all(path.is_file() for path in result.changed)


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    config, home = _config(tmp_path, monkeypatch)

    result = apply_config(config, dry_run=True)

    assert any("main.js" in str(path) for path in result.changed)
    assert not home.exists()


def test_apply_backs_up_existing_files(tmp_path, monkeypatch):
    config, home = _config(tmp_path, monkeypatch)
    target = home / ".config/noctalia/config.toml"
    target.parent.mkdir(parents=True)
    target.write_text("old noctalia settings\n")

    apply_config(config, runner=_noop)

    backups = list((home / ".local/state/rice/backups").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "config.toml").read_text() == "old noctalia settings\n"
    assert target.read_text() != "old noctalia settings\n"
    assert not list(home.rglob("*.tmp"))


def test_apply_runs_reload_and_enable_commands(tmp_path, monkeypatch):
    config, _ = _config(tmp_path, monkeypatch)
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)

    apply_config(config, runner=runner)

    assert ("systemctl", "--user", "daemon-reload") in calls
    assert (
        "systemctl",
        "--user",
        "enable",
        "--now",
        "rice-daemon.service",
        "rice-startup.service",
    ) in calls
    assert (
        "kwriteconfig6",
        "--file",
        "kwinrc",
        "--group",
        "Plugins",
        "--key",
        "rice-placementEnabled",
        "true",
    ) in calls
    assert ("qdbus6", "org.kde.KWin", "/KWin", "reconfigure") in calls
    assert ("noctalia", "msg", "config-reload") in calls


def test_apply_rejects_invalid_config(tmp_path, monkeypatch):
    config, _ = _config(tmp_path, monkeypatch)
    config.write_text("[meta]\nschema_version = 1\n")

    with pytest.raises(ValueError, match="missing section"):
        apply_config(config, runner=_noop)
