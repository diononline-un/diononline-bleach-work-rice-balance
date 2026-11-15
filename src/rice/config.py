import os
import tempfile
import tomllib
from copy import deepcopy
from pathlib import Path

import tomli_w

REQUIRED_TOP_LEVEL = ("meta", "output", "zone", "app", "placement", "activities")


def load_config(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def save_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = tomli_w.dumps(config)
    fd, temp_name = tempfile.mkstemp(prefix=".rice-", suffix=".toml", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _ids(items):
    return [item.get("id") for item in items]


def validate_config(config: dict) -> list[str]:
    errors = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in config:
            errors.append(f"missing section: {key}")
    if errors:
        return errors

    output_ids = set(filter(None, _ids(config["output"])))
    zone_ids = set(filter(None, _ids(config["zone"])))
    app_ids = set(filter(None, _ids(config["app"])))
    activity_ids = set(config["activities"])

    if len(output_ids) != len(config["output"]):
        errors.append("output ids must be present and unique")
    if len(zone_ids) != len(config["zone"]):
        errors.append("zone ids must be present and unique")
    if len(app_ids) != len(config["app"]):
        errors.append("app ids must be present and unique")

    for zone in config["zone"]:
        if zone.get("output") not in output_ids:
            errors.append(f"zone {zone.get('id')} references unknown output")
        if zone.get("kind") not in {"app", "shell"}:
            errors.append(f"zone {zone.get('id')} has invalid kind")
        x, y, w, h = (zone.get(name, 0) for name in ("x", "y", "w", "h"))
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1 or y + h > 1:
            errors.append(f"zone {zone.get('id')} is outside 0..1 bounds")

    for placement in config["placement"]:
        if placement.get("app") not in app_ids:
            errors.append(f"placement references unknown app {placement.get('app')}")
        if placement.get("zone") not in zone_ids:
            errors.append(f"placement references unknown zone {placement.get('zone')}")
        if placement.get("activity") not in activity_ids:
            errors.append(f"placement references unknown activity {placement.get('activity')}")
        if placement.get("mode") not in {"normal", "maximized", "fullscreen"}:
            errors.append(f"placement for {placement.get('app')} has invalid mode")

    for app in config["app"]:
        command = app.get("command", [])
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            errors.append(f"app {app.get('id')} has invalid command argv")

    for startup_key in ("always", "private"):
        for app_id in config.get("startup", {}).get(startup_key, []):
            if app_id not in app_ids:
                errors.append(f"startup.{startup_key} references unknown app {app_id}")

    for role, section in config.get("autostart", {}).items():
        if role not in activity_ids:
            errors.append(f"autostart role {role} has no activity")
        for app_id in section.get("apps", []):
            if app_id not in app_ids:
                errors.append(f"autostart.{role} references unknown app {app_id}")

    widgets = config.get("desktop_widget", [])
    if not isinstance(widgets, list):
        errors.append("desktop_widget must be a list")
        widgets = []
    for widget in widgets:
        if not isinstance(widget, dict):
            errors.append("desktop_widget entries must be objects")
            continue
        if not widget.get("plugin"):
            errors.append("desktop_widget has empty plugin")
        if widget.get("zone") not in zone_ids:
            errors.append(
                f"desktop_widget references unknown zone {widget.get('zone')}"
            )

    return errors
