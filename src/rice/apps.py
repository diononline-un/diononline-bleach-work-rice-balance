import tomllib
from pathlib import Path

SLOT_IDS = {
    "work_browser": "work-browser",
    "private_browser": "private-browser",
    "claude": "claude",
    "terminal": "terminal",
}


def load_catalog(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def resolve_choices(catalog: dict, choices: dict) -> dict:
    apps = {}
    for slot, variants in catalog.items():
        if slot == "toggles":
            continue
        selected = choices.get(slot)
        if selected not in variants:
            raise ValueError(f"invalid choice for {slot}: {selected}")
        entry = dict(variants[selected])
        entry["id"] = SLOT_IDS.get(slot, slot)
        apps[entry["id"]] = entry

    for app_id, entry in catalog.get("toggles", {}).items():
        if choices.get(app_id):
            selected = dict(entry)
            selected["id"] = app_id.replace("_", "-")
            apps[selected["id"]] = selected
    return apps


def app_commands(apps: dict) -> dict[str, list[str]]:
    return {app_id: app["command"] for app_id, app in apps.items()}
