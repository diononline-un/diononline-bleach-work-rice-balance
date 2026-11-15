"""Wallpaper discovery and theme rotation for the rice session.

The repository ships metadata only; wallpapers live in a user-selected
directory. Rotation state is stored in ``$XDG_STATE_HOME/rice/theme-current``
so the same image is not selected twice in a row.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

from .paths import state_home

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}
MARKER = "rice/theme-current"
NOCTALIA = "noctalia"


def list_wallpapers(directory: Path) -> list[Path]:
    """Return supported image files in ``directory``, sorted by name."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED
        ),
        key=lambda path: path.name,
    )


def wallpaper_status(directory: Path) -> dict:
    """Describe the wallpaper directory without touching the session."""
    files = list_wallpapers(directory)
    return {
        "directory": str(directory),
        "count": len(files),
        "files": [path.name for path in files],
    }


def marker_path() -> Path:
    return state_home() / MARKER


def _current() -> Path | None:
    try:
        text = marker_path().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(text) if text else None


def _wallpaper_dir(runtime: dict) -> Path:
    value = runtime.get("theme", {}).get("wallpaper_dir")
    if not value:
        raise ValueError("theme.wallpaper_dir is not configured")
    return Path(os.path.expandvars(str(value))).expanduser().resolve()


def _outputs(runtime: dict) -> list[str]:
    theme = runtime.get("theme", {})
    outputs = list(theme.get("outputs") or [])
    if not outputs:
        raise ValueError("theme.outputs is empty; apply the configuration first")
    if not all(isinstance(output, str) and output for output in outputs):
        raise ValueError("theme.outputs must be a list of non-empty strings")
    if theme.get("same_image_all_outputs", True) is False:
        raise ValueError(
            "theme.same_image_all_outputs = false is not supported yet; "
            "per-output wallpaper sets are not implemented"
        )
    return outputs


def _write_marker(path: Path) -> None:
    marker = marker_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".theme-", dir=marker.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(str(path))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, marker)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _apply(runtime: dict, path: Path, runner=None) -> Path:
    """Set one wallpaper on every configured output and record it."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    outputs = _outputs(runtime)
    run = runner or subprocess.run
    for output in outputs:
        run([NOCTALIA, "msg", "wallpaper-set", output, str(path)], check=True)
    _write_marker(path)
    return path


def _rotation_files(runtime: dict) -> list[Path]:
    _outputs(runtime)
    directory = _wallpaper_dir(runtime)
    files = list_wallpapers(directory)
    if not files:
        raise FileNotFoundError(f"no wallpapers in {directory}")
    return files


def _rotate(runtime: dict, step: int, runner=None) -> Path:
    files = _rotation_files(runtime)
    current = _current()
    if current in files:
        index = files.index(current) + step
    else:
        index = 0
    return _apply(runtime, files[index % len(files)], runner)


def next_theme(runtime: dict, runner=None) -> Path:
    """Apply the next wallpaper in sorted order, wrapping at the end."""
    return _rotate(runtime, 1, runner)


def previous_theme(runtime: dict, runner=None) -> Path:
    """Apply the previous wallpaper in sorted order, wrapping at the start."""
    return _rotate(runtime, -1, runner)


def _guarded() -> bool:
    """Return True when a fullscreen window or idle session pauses rotation."""
    commands = [
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.rice.Rice",
            "--object-path",
            "/Rice",
            "--method",
            "org.rice.Rice.FullscreenActive",
        ],
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.ScreenSaver",
            "--object-path",
            "/ScreenSaver",
            "--method",
            "org.freedesktop.ScreenSaver.GetActive",
        ],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except OSError:
            continue
        if "true" in result.stdout.lower():
            return True
    session_id = os.environ.get("XDG_SESSION_ID", "")
    if not session_id:
        return False
    try:
        result = subprocess.run(
            ["loginctl", "show-session", session_id, "-p", "IdleHint"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return "IdleHint=yes" in result.stdout


def hourly_theme(runtime: dict, runner=None, guard=None) -> Path | None:
    """Rotate hourly unless fullscreen or idle pauses the theme engine."""
    guard = guard or _guarded
    if guard():
        return None
    return next_theme(runtime, runner)


def _noctalia_ready() -> bool:
    try:
        return (
            subprocess.run(
                [NOCTALIA, "msg", "status"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


def boot_theme(
    runtime: dict,
    runner=None,
    ready=None,
    sleep=None,
    attempts: int = 60,
) -> Path:
    """Wait briefly for Noctalia, then apply the first theme after boot."""
    _rotation_files(runtime)
    ready = ready or _noctalia_ready
    sleep = sleep or time.sleep
    for _ in range(attempts):
        if ready():
            break
        sleep(1)
    return next_theme(runtime, runner)
