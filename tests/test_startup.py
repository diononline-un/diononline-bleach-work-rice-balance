import pytest

from rice.startup import clear_session_markers, run_autostart, run_startup

RUNTIME = {
    "apps": {
        "browser": {"command": ["browser"], "wm_class": "browser"},
        "editor": {"command": ["editor"], "wm_class": "editor"},
    },
    "startup": {"always": ["editor"], "private": ["browser"]},
    "autostart": {"private": {"apps": []}, "work": {"apps": ["browser"]}},
}


def test_startup_launches_always_and_private(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    launched = []
    run_startup(RUNTIME, launcher=lambda command: launched.append(command))
    assert launched == [["editor"], ["browser"]]


def test_autostart_work_runs_once(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    launched = []
    assert run_autostart(RUNTIME, "work", launcher=lambda command: launched.append(command)) == ["browser"]
    assert run_autostart(RUNTIME, "work", launcher=lambda command: launched.append(command)) == []
    assert launched == [["browser"]]


def test_session_markers_live_under_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    run_autostart(RUNTIME, "work", launcher=lambda command: None)
    assert (tmp_path / "rice" / "autostart-work.done").is_file()


def test_clear_session_markers_allows_relaunch(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    launched = []
    run_autostart(RUNTIME, "work", launcher=lambda command: launched.append(command))
    clear_session_markers()
    assert run_autostart(RUNTIME, "work", launcher=lambda command: launched.append(command)) == ["browser"]
    assert launched == [["browser"], ["browser"]]


def test_unknown_app_reports_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    runtime = {"apps": {}, "startup": {"always": ["missing"], "private": []}}
    with pytest.raises(ValueError, match="missing"):
        run_startup(runtime, launcher=lambda command: None)


def test_role_cannot_escape_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="role"):
        run_autostart(RUNTIME, "../escape", launcher=lambda command: None)

