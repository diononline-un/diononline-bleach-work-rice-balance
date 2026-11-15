import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [str(ROOT / "bin" / "rice"), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_version():
    result = run_cli("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == "rice 0.1.0"


def test_cli_has_core_commands():
    result = run_cli("--help")
    assert result.returncode == 0
    for command in ("apply", "startup", "activity", "daemon", "doctor", "theme"):
        assert command in result.stdout


def test_doctor_reports_problems(monkeypatch, capsys):
    import shutil

    from rice import cli, config, outputs

    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(outputs, "detect_outputs", lambda: [])
    monkeypatch.setattr(config, "load_config", lambda path: {})
    monkeypatch.setattr(
        config, "validate_config", lambda loaded: ["missing section: meta"]
    )

    assert cli.run_doctor(None) == 1

    out = capsys.readouterr().out
    assert "noctalia is not installed" in out
    assert "qdbus6 is not installed" in out
    assert "no detected outputs" in out
    assert "missing section: meta" in out


def test_doctor_returns_zero_when_healthy(monkeypatch, capsys):
    import shutil

    from rice import cli, config, outputs

    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(outputs, "detect_outputs", lambda: [object()])
    monkeypatch.setattr(config, "load_config", lambda path: {})
    monkeypatch.setattr(config, "validate_config", lambda loaded: [])

    assert cli.run_doctor(None) == 0
    assert capsys.readouterr().out.strip() == "rice doctor: OK"
