import subprocess
from pathlib import Path

import pytest

from rice.theme import (
    boot_theme,
    hourly_theme,
    index_path,
    list_wallpapers,
    next_theme,
    panel_active,
    previous_theme,
    refresh_cache,
    set_theme,
    toggle_panel,
    wallpaper_status,
)


def _runtime(tmp_path, monkeypatch, wallpapers, outputs=("DP-1",)):
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    directory = tmp_path / "wallpapers"
    directory.mkdir(exist_ok=True)
    for name in wallpapers:
        (directory / name).write_bytes(b"x")
    return {
        "theme": {
            "wallpaper_dir": str(directory),
            "outputs": list(outputs),
            "same_image_all_outputs": True,
        }
    }


class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))


def _marker(tmp_path):
    return tmp_path / "state/rice/theme-current"


def test_list_wallpapers_filters_images(tmp_path: Path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    assert [path.name for path in list_wallpapers(tmp_path)] == ["a.png", "b.jpg"]


def test_list_wallpapers_supports_jpeg_and_webp_and_sorts(tmp_path: Path):
    for name in ("z.webp", "m.JPEG", "a.PNG"):
        (tmp_path / name).write_bytes(b"x")
    assert [path.name for path in list_wallpapers(tmp_path)] == ["a.PNG", "m.JPEG", "z.webp"]


def test_list_wallpapers_missing_directory_is_empty(tmp_path: Path):
    assert list_wallpapers(tmp_path / "absent") == []


def test_wallpaper_status_counts_missing(tmp_path: Path):
    status = wallpaper_status(tmp_path)
    assert status["count"] == 0
    assert status["directory"] == str(tmp_path)
    assert status["files"] == []


def test_wallpaper_status_uses_cache_index(tmp_path):
    (tmp_path / "one.png").write_bytes(b"x")
    status = wallpaper_status(tmp_path)
    assert status["count"] == 1


def test_wallpaper_status_lists_files(tmp_path: Path):
    (tmp_path / "a.png").write_bytes(b"x")
    status = wallpaper_status(tmp_path)
    assert status["count"] == 1
    assert status["files"] == ["a.png"]


def test_next_theme_starts_at_first_sorted_file(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["b.png", "a.jpg"])
    runner = Runner()

    target = next_theme(runtime, runner=runner)

    assert target.name == "a.jpg"
    assert runner.calls == [
        (
            ["noctalia", "msg", "wallpaper-set", "DP-1", str(target)],
            {"check": True},
        )
    ]
    assert _marker(tmp_path).read_text() == str(target)


def test_next_theme_advances_and_wraps(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png", "b.png"])
    runner = Runner()

    assert next_theme(runtime, runner=runner).name == "a.png"
    assert next_theme(runtime, runner=runner).name == "b.png"
    assert next_theme(runtime, runner=runner).name == "a.png"
    assert len(runner.calls) == 3


def test_previous_theme_moves_backwards_and_wraps(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png", "b.png", "c.png"])
    runner = Runner()

    assert previous_theme(runtime, runner=runner).name == "a.png"
    assert previous_theme(runtime, runner=runner).name == "c.png"
    assert previous_theme(runtime, runner=runner).name == "b.png"


def test_rotation_ignores_stale_marker(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png", "b.png"])
    _marker(tmp_path).parent.mkdir(parents=True)
    _marker(tmp_path).write_text(str(tmp_path / "wallpapers/gone.png"))

    assert next_theme(runtime, runner=Runner()).name == "a.png"


def test_rotation_applies_to_every_output(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"], outputs=("DP-1", "HDMI-1"))
    runner = Runner()

    target = next_theme(runtime, runner=runner)

    assert [call[0][3] for call in runner.calls] == ["DP-1", "HDMI-1"]
    assert all(call[0][4] == str(target) for call in runner.calls)


def test_rotation_requires_outputs(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"], outputs=())
    runner = Runner()

    with pytest.raises(ValueError, match="outputs"):
        next_theme(runtime, runner=runner)
    assert runner.calls == []
    assert not _marker(tmp_path).exists()


def test_rotation_rejects_unimplemented_per_output_sets(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    runtime["theme"]["same_image_all_outputs"] = False

    with pytest.raises(ValueError, match="same_image_all_outputs"):
        next_theme(runtime, runner=Runner())


def test_rotation_requires_wallpapers(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, [])

    with pytest.raises(FileNotFoundError):
        next_theme(runtime, runner=Runner())


def test_rotation_expands_environment_variables(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    directory = runtime["theme"]["wallpaper_dir"]
    monkeypatch.setenv("RICE_TEST_WALLPAPERS", directory)
    runtime["theme"]["wallpaper_dir"] = "$RICE_TEST_WALLPAPERS"

    assert next_theme(runtime, runner=Runner()).name == "a.png"


def test_hourly_theme_respects_guard(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    runner = Runner()

    assert hourly_theme(runtime, runner=runner, guard=lambda: True) is None
    assert runner.calls == []
    assert not _marker(tmp_path).exists()


def test_hourly_theme_rotates_when_unguarded(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png", "b.png"])
    runner = Runner()

    assert hourly_theme(runtime, runner=runner, guard=lambda: False).name == "a.png"
    assert len(runner.calls) == 1


def test_boot_theme_waits_for_noctalia_then_rotates(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    runner = Runner()
    ready = iter([False, False, True])
    sleeps = []

    target = boot_theme(
        runtime,
        runner=runner,
        ready=lambda: next(ready),
        sleep=sleeps.append,
    )

    assert target.name == "a.png"
    assert sleeps == [1, 1]
    assert len(runner.calls) == 1


def test_boot_theme_gives_up_waiting_and_still_rotates(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    sleeps = []

    target = boot_theme(
        runtime,
        runner=Runner(),
        ready=lambda: False,
        sleep=sleeps.append,
        attempts=2,
    )

    assert target.name == "a.png"
    assert sleeps == [1, 1]


def test_boot_theme_fails_fast_without_outputs(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"], outputs=())
    ready_calls = []

    with pytest.raises(ValueError, match="outputs"):
        boot_theme(
            runtime,
            runner=Runner(),
            ready=lambda: ready_calls.append(True),
            sleep=lambda seconds: None,
        )
    assert ready_calls == []


def _cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    return cache


def test_refresh_cache_writes_tab_separated_index(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["b.png", "a.jpg"])
    cache = _cache(tmp_path, monkeypatch)
    drawn = []

    def thumbnail(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"jpeg")
        drawn.append((Path(source).name, Path(target).name))

    entries = refresh_cache(
        runtime, which=lambda name: "/usr/bin/magick", thumbnail=thumbnail
    )

    lines = index_path().read_text(encoding="utf-8").splitlines()
    assert [entry["name"] for entry in entries] == ["a", "b"]
    assert len(lines) == 2
    for line, name in zip(lines, ("a", "b")):
        source, thumb, label = line.split("\t")
        assert Path(source).name in {"a.jpg", "b.png"}
        assert Path(thumb).is_file()
        assert label == name
    assert [name for name, _ in drawn] == ["a.jpg", "b.png"]
    assert list((cache / "rice-theme").glob(".index-*")) == []


def test_refresh_cache_requires_magick(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    _cache(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match="ImageMagick"):
        refresh_cache(runtime, which=lambda name: None)


def test_set_theme_resolves_relative_path_under_wallpaper_dir(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    runner = Runner()

    target = set_theme(runtime, "a.png", runner=runner)

    assert target == (tmp_path / "wallpapers/a.png").resolve()
    assert runner.calls[0][0][4] == str(target)
    assert _marker(tmp_path).read_text() == str(target)


def test_set_theme_rejects_paths_outside_wallpaper_dir(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path, monkeypatch, ["a.png"])
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")

    with pytest.raises(ValueError, match="outside"):
        set_theme(runtime, str(outside), runner=Runner())


class PanelRunner:
    def __init__(self, active=False):
        self.active = active
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[1:] == ["msg", "status"]:
            state = "rice/themes:panel" if self.active else ""
            output = f'"activePanelId": "{state}"'
            return subprocess.CompletedProcess(command, 0, output, "")
        return subprocess.CompletedProcess(command, 0, "", "")


def test_panel_active_detects_open_theme_panel():
    assert panel_active(PanelRunner(active=True)) is True
    assert panel_active(PanelRunner(active=False)) is False


def test_panel_active_is_false_without_noctalia():
    def missing(command, **kwargs):
        raise FileNotFoundError("noctalia")

    assert panel_active(missing) is False


def test_toggle_panel_opens_when_closed():
    runner = PanelRunner(active=False)

    assert toggle_panel(runner) is True
    assert runner.calls == [
        ["noctalia", "msg", "status"],
        ["noctalia", "msg", "panel-close"],
        ["noctalia", "msg", "panel-open", "rice/themes:panel"],
    ]


def test_toggle_panel_closes_when_open():
    runner = PanelRunner(active=True)

    assert toggle_panel(runner) is False
    assert runner.calls == [
        ["noctalia", "msg", "status"],
        ["noctalia", "msg", "panel-close"],
    ]
