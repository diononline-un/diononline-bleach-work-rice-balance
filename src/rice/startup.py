import os
import subprocess
from pathlib import Path


def _runtime_root() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        raise RuntimeError("XDG_RUNTIME_DIR is not set; cannot store session markers")
    root = Path(base) / "rice"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_launcher(command: list[str]):
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def launch(command: list[str]) -> None:
    """Launch one command detached from the calling process."""
    _default_launcher(command)


def terminal_command(runtime: dict) -> list[str] | None:
    """Return the configured terminal argv, or None when no terminal exists."""
    app = runtime.get("apps", {}).get("terminal")
    if isinstance(app, dict) and app.get("command"):
        return list(app["command"])
    return None


def _commands(runtime: dict, app_ids: list[str]) -> list[list[str]]:
    apps = runtime.get("apps", {})
    commands = []
    for app_id in app_ids:
        app = apps.get(app_id)
        if not isinstance(app, dict) or not app.get("command"):
            raise ValueError(f"runtime config has no launchable app {app_id!r}")
        commands.append(app["command"])
    return commands


def _launch(runtime: dict, app_ids: list[str], launcher) -> list[str]:
    """Launch every app id and return the ids that were launched."""
    for command in _commands(runtime, app_ids):
        launcher(command)
    return list(app_ids)


def _marker_path(name: str) -> Path:
    return _runtime_root() / f"{name}.done"


def run_startup(runtime: dict, launcher=_default_launcher) -> list[str]:
    startup = runtime.get("startup", {})
    launched = []
    launched.extend(_launch(runtime, startup.get("always", []), launcher))
    launched.extend(_launch(runtime, startup.get("private", []), launcher))
    _marker_path("startup").write_text("1")
    return launched


def run_autostart(runtime: dict, role: str, launcher=_default_launcher) -> list[str]:
    if not role or Path(role).name != role:
        raise ValueError(f"invalid activity role {role!r}")
    marker = _marker_path(f"autostart-{role}")
    if marker.exists():
        return []
    app_ids = runtime.get("autostart", {}).get(role, {}).get("apps", [])
    launched = _launch(runtime, app_ids, launcher)
    marker.write_text("1")
    return launched


def clear_session_markers() -> None:
    for marker in _runtime_root().glob("*.done"):
        marker.unlink()
