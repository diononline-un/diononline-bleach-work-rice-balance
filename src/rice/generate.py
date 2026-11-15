import json
import tomllib
from pathlib import Path

import tomli_w

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "kwin" / "main.js.in"
ARRANGE_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / "kwin" / "arrange.js.in"
)
NOCTALIA_BASE = (
    Path(__file__).resolve().parents[2] / "defaults" / "noctalia" / "config.toml"
)
SYSTEMD_UNITS = {
    "rice-daemon.service": "rice daemon",
    "rice-startup.service": "rice startup",
    "rice-theme-boot.service": "rice theme boot",
    "rice-theme-hourly.service": "rice theme hourly",
    "rice-theme-hourly.timer": "",
    "rice-shortcuts.service": "rice shortcuts disable-conflicts",
}


def _zone(config: dict, zone_id: str) -> dict:
    zone = next((item for item in config.get("zone", []) if item["id"] == zone_id), None)
    if zone is None:
        raise ValueError(f"placement references unknown zone: {zone_id}")
    output = next(
        (item for item in config.get("output", []) if item["id"] == zone["output"]),
        None,
    )
    if output is None:
        raise ValueError(f"zone {zone_id} references unknown output: {zone['output']}")
    return {
        "output": output["connector"],
        "zone": {
            key: zone.get(key, 0 if key == "gap_px" else 0.0)
            for key in ("x", "y", "w", "h", "gap_px")
        },
    }


def kwin_rules(config: dict) -> list[dict]:
    apps = {app["id"]: app for app in config.get("app", [])}
    activities = {
        role: data.get("kde_id", "") or ""
        for role, data in config.get("activities", {}).items()
    }
    rules = []
    for placement in config.get("placement", []):
        app = apps.get(placement["app"])
        if app is None:
            continue
        resolved = _zone(config, placement["zone"])
        rules.append({
            "wm_class": str(app.get("wm_class") or "").lower(),
            "match_title": str(placement.get("match_title") or "").lower(),
            "activity": activities.get(placement["activity"], ""),
            "mode": placement["mode"],
            "priority": placement.get("priority", 0),
            **resolved,
        })
    # Highest priority first; on ties the later placement wins.
    ordered = sorted(
        enumerate(rules),
        key=lambda pair: (pair[1]["priority"], pair[0]),
        reverse=True,
    )
    return [rule for _, rule in ordered]


def output_roles(config: dict) -> list[dict]:
    """Map configured output roles to connectors for the KWin shortcut block."""
    return [
        {"role": output["role"], "connector": output["connector"]}
        for output in config.get("output", [])
        if output.get("role") and output.get("connector")
    ]


def generate_kwin(config: dict) -> str:
    rules = kwin_rules(config)
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__RULES__", json.dumps(rules, indent=2))
        .replace("__OUTPUTS__", json.dumps(output_roles(config), indent=2))
    )


def generate_arrange(config: dict) -> str:
    """Generate the one-shot layout reapply script loaded by ``rice arrange``."""
    rules = kwin_rules(config)
    return ARRANGE_TEMPLATE.read_text(encoding="utf-8").replace(
        "__RULES__", json.dumps(rules, indent=2)
    )


def _widget_anchor(config: dict, widget: dict) -> dict:
    zone_id = widget.get("zone")
    zone = next((item for item in config.get("zone", []) if item["id"] == zone_id), None)
    if zone is None:
        raise ValueError(f"desktop widget references unknown zone: {zone_id}")
    output = next(
        (item for item in config.get("output", []) if item["id"] == zone["output"]),
        None,
    )
    if output is None:
        raise ValueError(f"zone {zone_id} references unknown output: {zone['output']}")
    return {
        "type": widget["plugin"],
        "output": output["connector"],
        "cx": round(
            output.get("x", 0)
            + output.get("width", 0) * (zone.get("x", 0) + zone.get("w", 0) / 2),
            1,
        ),
        "cy": round(
            output.get("y", 0)
            + output.get("height", 0) * (zone.get("y", 0) + zone.get("h", 0) / 2),
            1,
        ),
        "scale": widget.get("scale", 1.0),
    }


def load_noctalia_base() -> dict:
    with NOCTALIA_BASE.open("rb") as handle:
        return tomllib.load(handle)


def generate_noctalia(config: dict) -> str:
    data = load_noctalia_base()
    widgets = [
        _widget_anchor(config, widget) for widget in config.get("desktop_widget", [])
    ]
    data["desktop_widgets"] = {
        "enabled": True,
        "schema_version": 2,
        "widget_order": [f"rice_{index}" for index in range(len(widgets))],
        "widget": {f"rice_{index}": widget for index, widget in enumerate(widgets)},
    }
    return tomli_w.dumps(data)


def generate_runtime(config: dict) -> dict:
    return {
        "startup": config.get("startup", {}),
        "autostart": config.get("autostart", {}),
        "apps": {app["id"]: app for app in config.get("app", [])},
        "zones": {zone["id"]: zone for zone in config.get("zone", [])},
        "activities": config.get("activities", {}),
        "theme": config.get("theme", {}),
    }


def generate_systemd(config: dict, install_root: Path) -> dict[Path, str]:
    template_dir = Path(install_root) / "templates" / "systemd"
    units = {}
    for filename, command in SYSTEMD_UNITS.items():
        text = (template_dir / f"{filename}.in").read_text(encoding="utf-8")
        units[Path(filename)] = text.replace("@RICE_COMMAND@", command)
    return units
