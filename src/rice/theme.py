"""Wallpaper discovery and theme rotation for the rice session.

The repository ships metadata only; wallpapers live in a user-selected
directory. Rotation state is stored in ``$XDG_STATE_HOME/rice/theme-current``
so the same image is not selected twice in a row.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .paths import cache_home, state_home

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}
MARKER = "rice/theme-current"
NOCTALIA = "noctalia"
PANEL = "rice/themes:panel"
THUMBNAIL_SIZE = "480x270"
THUMBNAIL_COMMAND = "magick"


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


def cache_dir() -> Path:
    return cache_home() / "rice-theme"


def index_path() -> Path:
    return cache_dir() / "index.tsv"


def thumbnails_dir() -> Path:
    return cache_dir() / "thumbs"


def current_theme() -> Path | None:
    """Return the last applied wallpaper path, if one is recorded."""
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


def set_theme(runtime: dict, value: str | Path, runner=None) -> Path:
    """Apply one wallpaper named relative to ``theme.wallpaper_dir``."""
    directory = _wallpaper_dir(runtime)
    candidate = Path(os.path.expandvars(str(value))).expanduser()
    if not candidate.is_absolute():
        candidate = directory / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(directory):
        raise ValueError(f"theme path is outside {directory}: {value}")
    return _apply(runtime, candidate, runner)


def _thumbnail_name(source: Path) -> str:
    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem) or "theme"
    return f"{stem}-{digest}.jpg"


def make_thumbnail(source: Path, target: Path) -> None:
    """Render a 480x270 JPEG thumbnail with ImageMagick."""
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            THUMBNAIL_COMMAND,
            str(source),
            "-auto-orient",
            "-resize",
            f"{THUMBNAIL_SIZE}^",
            "-gravity",
            "center",
            "-extent",
            THUMBNAIL_SIZE,
            "-strip",
            "-quality",
            "82",
            str(target),
        ],
        check=True,
    )


def refresh_cache(runtime: dict, which=None, thumbnail=None) -> list[dict]:
    """Build the panel cache index and JPEG thumbnails atomically."""
    directory = _wallpaper_dir(runtime)
    files = list_wallpapers(directory)
    which = which or shutil.which
    if not which(THUMBNAIL_COMMAND):
        raise RuntimeError(
            f"{THUMBNAIL_COMMAND} (ImageMagick) is required for theme thumbnails"
        )
    render = thumbnail or make_thumbnail
    thumbs = thumbnails_dir()
    thumbs.mkdir(parents=True, exist_ok=True)
    index = index_path()
    index.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    fd, temp_name = tempfile.mkstemp(prefix=".index-", dir=index.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            for source in files:
                target = thumbs / _thumbnail_name(source)
                stale = (
                    not target.is_file()
                    or source.stat().st_mtime > target.stat().st_mtime
                )
                if stale:
                    render(source, target)
                if not target.is_file():
                    continue
                stream.write(f"{source}\t{target}\t{source.stem}\n")
                entries.append(
                    {
                        "source": str(source),
                        "thumbnail": str(target),
                        "name": source.stem,
                    }
                )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, index)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return entries


def panel_active(runner=None) -> bool:
    """Return True when Noctalia reports the theme panel as open."""
    run = runner or subprocess.run
    try:
        result = run(
            [NOCTALIA, "msg", "status"], capture_output=True, text=True, check=False
        )
    except OSError:
        return False
    text = getattr(result, "stdout", "") or ""
    return f'"activePanelId": "{PANEL}"' in text


def toggle_panel(runner=None) -> bool:
    """Close the theme panel when open, otherwise open it. Returns opened state."""
    run = runner or subprocess.run
    if panel_active(run):
        run([NOCTALIA, "msg", "panel-close"], check=True)
        return False
    try:
        run([NOCTALIA, "msg", "panel-close"], check=False)
    except OSError:
        # A missing panel or IPC socket is fine before opening.
        pass
    run([NOCTALIA, "msg", "panel-open", PANEL], check=True)
    return True


def _rotation_files(runtime: dict) -> list[Path]:
    _outputs(runtime)
    directory = _wallpaper_dir(runtime)
    files = list_wallpapers(directory)
    if not files:
        raise FileNotFoundError(f"no wallpapers in {directory}")
    return files


def _rotate(runtime: dict, step: int, runner=None) -> Path:
    files = _rotation_files(runtime)
    current = current_theme()
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
