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


def test_cli_help_lists_theme_panel_and_set():
    result = run_cli("theme", "--help")
    assert result.returncode == 0
    for value in ("set", "refresh", "panel", "status"):
        assert value in result.stdout


def test_cli_help_lists_cheatsheet_and_quickstart():
    result = run_cli("--help")
    assert "cheatsheet" in result.stdout
    assert "quickstart" in result.stdout
    assert "arrange" in result.stdout


def test_cheatsheet_toggles_panel(monkeypatch):
    from rice import cli

    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    assert cli.run_cheatsheet(None) == 0
    assert calls == [(["noctalia", "msg", "panel-toggle", "rice/cheatsheet:panel"],)]


def test_quickstart_launches_private_startup(monkeypatch):
    from rice import cli, startup

    runtime = {
        "activities": {
            "private": {"kde_id": "private-id"},
            "work": {"kde_id": "work-id"},
        },
        "startup": {"always": [], "private": []},
        "autostart": {},
    }
    launched = []
    monkeypatch.setattr(cli, "_runtime", lambda: runtime)
    monkeypatch.setattr(cli, "current_activity", lambda: "private-id")
    monkeypatch.setattr(
        startup, "run_startup", lambda data, launcher=None: launched.append("private")
    )
    monkeypatch.setattr(
        startup, "run_autostart", lambda data, role: launched.append(role)
    )

    assert cli.run_quickstart(None) == 0
    assert launched == ["private"]


def test_quickstart_launches_work_autostart(monkeypatch):
    from rice import cli, startup

    runtime = {
        "activities": {
            "private": {"kde_id": "private-id"},
            "work": {"kde_id": "work-id"},
        },
        "startup": {"always": [], "private": []},
        "autostart": {},
    }
    launched = []
    monkeypatch.setattr(cli, "_runtime", lambda: runtime)
    monkeypatch.setattr(cli, "current_activity", lambda: "work-id")
    monkeypatch.setattr(startup, "run_startup", lambda data, launcher=None: launched.append("private"))
    monkeypatch.setattr(startup, "run_autostart", lambda data, role: launched.append(role))

    assert cli.run_quickstart(None) == 0
    assert launched == ["work"]


def test_quickstart_rejects_unknown_activity(monkeypatch, capsys):
    from rice import cli

    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: {"activities": {"private": {"kde_id": "private-id"}}},
    )
    monkeypatch.setattr(cli, "current_activity", lambda: "someone-elses-id")

    assert cli.main(["quickstart"]) == 1
    captured = capsys.readouterr()
    assert "current KDE activity" in captured.err
    assert captured.err.count("\n") == 1


def test_arrange_reports_missing_kwin_method(monkeypatch, capsys):
    from rice import cli

    assert cli.main(["arrange"]) == 1
    captured = capsys.readouterr()
    assert "rice: " in captured.err
    assert "KWin" in captured.err
    assert "Traceback" not in captured.err


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


def test_main_reports_operational_errors_without_traceback(monkeypatch, capsys):
    from rice import apply, cli

    def fail(path, dry_run=False):
        raise ValueError("bad config")

    monkeypatch.setattr(apply, "apply_config", fail)

    assert cli.main(["apply"]) == 1

    captured = capsys.readouterr()
    assert captured.err.strip() == "rice: bad config"
    assert "bad config" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_main_reports_subprocess_errors_without_traceback(monkeypatch, capsys):
    import subprocess

    from rice import cli, theme

    def fail(runtime):
        raise subprocess.CalledProcessError(1, ["magick", "a.png"])

    monkeypatch.setattr(cli, "_runtime", lambda: {})
    monkeypatch.setattr(theme, "refresh_cache", fail)

    assert cli.main(["theme", "refresh"]) == 1

    captured = capsys.readouterr()
    assert captured.err.startswith("rice: ")
    assert len(captured.err.strip().splitlines()) == 1
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
