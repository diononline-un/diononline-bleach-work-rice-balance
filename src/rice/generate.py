import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "kwin" / "main.js.in"


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


def generate_kwin(config: dict) -> str:
    rules = kwin_rules(config)
    return TEMPLATE.read_text(encoding="utf-8").replace(
        "__RULES__", json.dumps(rules, indent=2)
    )
