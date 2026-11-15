from .outputs import Output


def choose_layout(outputs: list[Output]) -> str:
    if len(outputs) == 1 and outputs[0].width >= 3440:
        return "ultrawide"
    if len(outputs) >= 3:
        return "triple"
    return "single-split"


def _zone(id, output, kind, x, y, w, h):
    return {"id": id, "output": output, "kind": kind, "x": x, "y": y, "w": w, "h": h, "gap_px": 8}


def layout_config(preset: str, outputs: list[Output]) -> dict:
    main = next((output for output in outputs if output.primary), outputs[0])
    if preset == "ultrawide":
        zones = [
            _zone("edge-left", main.id, "shell", 0.0, 0.0, 0.20, 1.0),
            _zone("center-left", main.id, "app", 0.22, 0.0, 0.28, 1.0),
            _zone("center-right", main.id, "app", 0.50, 0.0, 0.28, 1.0),
            _zone("edge-right", main.id, "shell", 0.80, 0.0, 0.20, 1.0),
        ]
    elif preset == "triple":
        zones = [
            _zone("main-left", main.id, "app", 0.0, 0.0, 0.5, 1.0),
            _zone("main-right", main.id, "app", 0.5, 0.0, 0.5, 1.0),
            _zone("side-left", outputs[1].id, "app", 0.0, 0.0, 0.5, 1.0),
            _zone("side-right", outputs[1].id, "app", 0.5, 0.0, 0.5, 1.0),
            _zone("portrait-full", outputs[2].id, "app", 0.0, 0.0, 1.0, 1.0),
        ]
    else:
        zones = [
            _zone("center-left", main.id, "app", 0.0, 0.0, 0.5, 1.0),
            _zone("center-right", main.id, "app", 0.5, 0.0, 0.5, 1.0),
        ]
    return {"zone": zones}


def default_placements(preset: str, apps: dict) -> list[dict]:
    zones = {
        "triple": {
            "private": "main-left", "work": "main-left",
            "private_side": "side-left", "work_side": "side-right",
            "portrait": "portrait-full",
        },
        "ultrawide": {
            "private": "center-left", "work": "center-left",
            "private_side": "center-left", "work_side": "center-right",
            "portrait": "center-right",
        },
        "single-split": {
            "private": "center-left", "work": "center-left",
            "private_side": "center-left", "work_side": "center-right",
            "portrait": "center-right",
        },
    }[preset]
    rules = []
    mapping = {
        "private-browser": ("private", False),
        "work-browser": ("work", False),
        "steam": ("private", False),
        "youtube-music": ("private_side", False),
        "claude": ("private_side", False),
        "opencode": ("private_side", False),
        "terminal": ("private_side", False),
        "gpu-recorder": ("private_side", False),
        "discord": ("portrait", True),
        "slack": ("portrait", True),
        "hero-town": ("work_side", False),
    }
    for app_id, entry in apps.items():
        if app_id not in mapping:
            continue
        role, fullscreen = mapping[app_id]
        activities = entry.get("activities") or ["private"]
        for activity in activities:
            zone = zones[role]
            if app_id in {"opencode", "claude", "terminal", "gpu-recorder"} and activity == "work":
                zone = zones["work_side"]
            rules.append({
                "app": app_id,
                "activity": activity,
                "zone": zone,
                "mode": "fullscreen" if fullscreen else "normal",
            })
    return rules
