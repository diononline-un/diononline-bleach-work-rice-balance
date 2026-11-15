# Core Installer and Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core of a configurable KDE Plasma 6 + Noctalia rice for Arch/CachyOS: installer, TOML configuration, output/zone placement, generated KWin/Noctalia/systemd files, activity startup, and English documentation.

**Architecture:** `rice.toml` is the single source of truth. Python modules validate it, resolve outputs and applications, and generate KWin JavaScript, a Noctalia TOML include, systemd units, and a runtime JSON file. A D-Bus daemon handles activity switching and autostart; the local web configurator is a separate follow-up plan.

**Tech Stack:** Python 3.11+, `tomli-w`, `dbus-python`, KDE Plasma 6/KWin scripting, Noctalia 5.5+, systemd user units, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-core-design.md`

## Global Constraints

- Arch Linux or CachyOS only; require `pacman`, KDE Plasma 6, KWin, Noctalia 5.5+, and an existing `paru` or `yay`.
- Runtime Python dependencies: standard library, `python-tomli-w`, `python-dbus`, `python-gobject`.
- All user paths use `$HOME` and XDG variables. No literal `/home/<user>` in committed files.
- No personal links, personal hostnames, VPS endpoints, Tailscale names, tokens, or credentials.
- No wallpaper binaries in the repository.
- All documentation is English.
- No system-wide writes except package installation through `pacman`/AUR. No login-screen or boot-splash work in this plan.
- `rice.toml` is canonical; generated output is never edited manually.
- Every task ends with a passing test run and a commit.

---

## File Structure

```text
bin/rice
install.sh
uninstall.sh
defaults/rice.toml
defaults/apps.toml
defaults/layouts/triple.toml
defaults/layouts/single-split.toml
defaults/layouts/ultrawide.toml
src/rice/__init__.py
src/rice/cli.py
src/rice/config.py
src/rice/paths.py
src/rice/outputs.py
src/rice/layouts.py
src/rice/activities.py
src/rice/apps.py
src/rice/generate.py
src/rice/apply.py
src/rice/startup.py
src/rice/theme.py
src/rice/daemon.py
src/rice/installer.py
templates/kwin/main.js.in
templates/noctalia/rice.toml.in
templates/systemd/rice-daemon.service.in
templates/systemd/rice-startup.service.in
templates/systemd/rice-fullscreen-watch.service.in
templates/systemd/rice-theme-boot.service.in
templates/systemd/rice-theme-hourly.service.in
templates/systemd/rice-theme-hourly.timer.in
assets/wallpapers/manifest.toml
tests/test_cli.py
tests/test_config.py
tests/test_outputs.py
tests/test_layouts.py
tests/test_activities.py
tests/test_apps.py
tests/test_generate.py
tests/test_apply.py
tests/test_startup.py
tests/test_theme.py
tests/test_installer.py
tests/test_pii.py
```

### Task 1: Repository Scaffold and CLI

**Files:**
- Create: `bin/rice`
- Create: `src/rice/__init__.py`
- Create: `src/rice/cli.py`
- Create: `tests/test_cli.py`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: nothing.
- Produces: `rice --version` returns `rice 0.1.0`; `rice.cli.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [str(ROOT / "bin" / "rice"), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_version():
    result = run_cli("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == "rice 0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::test_version -v`  
Expected: FAIL because `bin/rice` does not exist.

- [ ] **Step 3: Write minimal implementation**

```bash
# bin/rice
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m rice.cli "$@"
```

```python
# src/rice/__init__.py
__version__ = "0.1.0"
```

```python
# src/rice/cli.py
import argparse

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rice")
    parser.add_argument("--version", action="version", version=f"rice {__version__}")
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```text
# requirements-dev.txt
pytest
```

```toml
# pyproject.toml
[project]
name = "rice"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["tomli-w", "dbus-python", "PyGObject"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Make `bin/rice` executable with `chmod +x bin/rice`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/rice src/rice/__init__.py src/rice/cli.py tests/test_cli.py pyproject.toml requirements-dev.txt
git commit -m "chore: scaffold rice cli"
```

---

### Task 2: Config Model, Validation, and Atomic TOML I/O

**Files:**
- Create: `src/rice/paths.py`
- Create: `src/rice/config.py`
- Create: `defaults/rice.toml`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_config(path: Path) -> dict`; `save_config(path: Path, config: dict) -> None`; `validate_config(config: dict) -> list[str]`; `config_path() -> Path`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from copy import deepcopy
from pathlib import Path

import pytest

from rice.config import load_config, save_config, validate_config

VALID = {
    "meta": {"schema_version": 1},
    "output": [{"id": "main", "role": "main", "connector": "DP-1", "primary": True}],
    "zone": [
        {"id": "left", "output": "main", "kind": "app", "x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8},
        {"id": "right", "output": "main", "kind": "app", "x": 0.5, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8},
    ],
    "app": [{"id": "browser", "name": "Browser", "command": ["firefox"], "wm_class": "firefox"}],
    "placement": [{"app": "browser", "activity": "private", "zone": "left", "mode": "normal"}],
    "activities": {"private": {"name": "Private", "kde_id": ""}, "work": {"name": "Work", "kde_id": ""}},
    "startup": {"always": [], "private": ["browser"]},
    "autostart": {"private": {"apps": []}, "work": {"apps": []}},
    "desktop_widget": [],
}


def test_validate_accepts_valid_config():
    assert validate_config(VALID) == []


@pytest.mark.parametrize("field", ["left", "right"])
def test_validate_rejects_zone_outside_bounds(field):
    config = deepcopy(VALID)
    config["zone"][0 if field == "left" else 1]["w"] = 0.8
    errors = validate_config(config)
    assert any("outside" in error for error in errors)


def test_validate_rejects_unknown_zone_reference():
    config = deepcopy(VALID)
    config["placement"][0]["zone"] = "missing"
    errors = validate_config(config)
    assert any("unknown zone" in error for error in errors)


def test_save_and_load_round_trip(tmp_path: Path):
    path = tmp_path / "rice.toml"
    save_config(path, VALID)
    assert load_config(path) == VALID
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`  
Expected: FAIL because `rice.config` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/paths.py
import os
from pathlib import Path


def xdg(env: str, fallback: str) -> Path:
    return Path(os.environ.get(env, str(Path.home() / fallback)))


def config_home() -> Path:
    return xdg("XDG_CONFIG_HOME", ".config")


def data_home() -> Path:
    return xdg("XDG_DATA_HOME", ".local/share")


def state_home() -> Path:
    return xdg("XDG_STATE_HOME", ".local/state")


def cache_home() -> Path:
    return xdg("XDG_CACHE_HOME", ".cache")


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user"))


def config_path() -> Path:
    return config_home() / "rice" / "rice.toml"
```

```python
# src/rice/config.py
import os
import tempfile
import tomllib
from copy import deepcopy
from pathlib import Path

import tomli_w

from .paths import config_path, data_home

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

    return errors
```

Create `defaults/rice.toml` containing the same keys as the test fixture, with the two center zones and no personal data.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/paths.py src/rice/config.py defaults/rice.toml tests/test_config.py
git commit -m "feat: add rice config model and validation"
```

---

### Task 3: Output Detection, Activities, and Layout Presets

**Files:**
- Create: `src/rice/outputs.py`
- Create: `src/rice/activities.py`
- Create: `src/rice/layouts.py`
- Create: `defaults/layouts/triple.toml`
- Create: `defaults/layouts/single-split.toml`
- Create: `defaults/layouts/ultrawide.toml`
- Test: `tests/test_outputs.py`
- Test: `tests/test_layouts.py`
- Test: `tests/test_activities.py`

**Interfaces:**
- Consumes: `rice.paths`, `rice.config`.
- Produces: `Output(id, connector, width, height, x, y, primary)`; `detect_outputs(json_text: str | None = None) -> list[Output]`; `choose_layout(outputs) -> str`; `layout_config(preset: str, outputs: list[Output]) -> dict`; `list_activities(runner=...) -> dict[str, str]`; `ensure_activity(name, runner=...) -> str`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_outputs.py
import json

from rice.outputs import detect_outputs

KScreen = {
    "outputs": [
        {"name": "DP-1", "connected": True, "enabled": True, "primary": True,
         "geometry": {"x": 0, "y": 0, "width": 5120, "height": 1440}},
        {"name": "HDMI-A-1", "connected": False, "enabled": False, "primary": False,
         "geometry": {"x": 0, "y": 0, "width": 1080, "height": 1920}},
    ]
}


def test_detect_outputs_filters_disconnected():
    outputs = detect_outputs(json.dumps(KScreen))
    assert [output.connector for output in outputs] == ["DP-1"]
    assert outputs[0].width == 5120
```

```python
# tests/test_layouts.py
from rice.layouts import choose_layout, layout_config
from rice.outputs import Output


def test_single_wide_chooses_ultrawide():
    assert choose_layout([Output("main", "DP-1", 5120, 1440, 0, 0, True)]) == "ultrawide"


def test_ultrawide_has_two_center_app_zones():
    outputs = [Output("main", "DP-1", 5120, 1440, 0, 0, True)]
    config = layout_config("ultrawide", outputs)
    app_zones = [zone["id"] for zone in config["zone"] if zone["kind"] == "app"]
    assert "center-left" in app_zones
    assert "center-right" in app_zones
```

```python
# tests/test_activities.py
from rice.activities import ensure_activity, list_activities


def fake_runner(args):
    if "ListActivities" in args:
        return "private-uuid\nwork-uuid\n"
    if "ActivityName" in args:
        return {"private-uuid": "Private", "work-uuid": "Work"}[args[-1]]
    if "CreateActivity" in args:
        return "new-uuid\n"
    raise AssertionError(args)


def test_list_activities_maps_names():
    assert list_activities(fake_runner) == {"Private": "private-uuid", "Work": "work-uuid"}


def test_ensure_activity_creates_missing():
    assert ensure_activity("Games", fake_runner) == "new-uuid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_outputs.py tests/test_layouts.py tests/test_activities.py -v`  
Expected: FAIL because modules do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/outputs.py
import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Output:
    id: str
    connector: str
    width: int
    height: int
    x: int
    y: int
    primary: bool


def _default_json() -> str:
    return subprocess.run(
        ["kscreen-doctor", "-j"], capture_output=True, text=True, check=True
    ).stdout


def detect_outputs(json_text: str | None = None) -> list[Output]:
    data = json.loads(json_text if json_text is not None else _default_json())
    result = []
    for index, item in enumerate(data.get("outputs", [])):
        if not item.get("connected") or not item.get("enabled"):
            continue
        geometry = item.get("geometry", {})
        result.append(Output(
            id="main" if item.get("primary") else f"output-{index + 1}",
            connector=item["name"],
            width=int(geometry.get("width", 0)),
            height=int(geometry.get("height", 0)),
            x=int(geometry.get("x", 0)),
            y=int(geometry.get("y", 0)),
            primary=bool(item.get("primary")),
        ))
    return result
```

```python
# src/rice/activities.py
import subprocess

ACTIVITY_SERVICE = "org.kde.ActivityManager"
ACTIVITY_PATH = "/ActivityManager/Activities"
ACTIVITY_IFACE = "org.kde.ActivityManager.Activities"


def _qdbus(args) -> str:
    return subprocess.run(
        ["qdbus6", ACTIVITY_SERVICE, ACTIVITY_PATH, ACTIVITY_IFACE, *args],
        capture_output=True, text=True, check=True
    ).stdout.strip()


def list_activities(runner=None) -> dict[str, str]:
    runner = runner or _qdbus
    ids = [line.strip() for line in runner(["ListActivities"]).splitlines() if line.strip()]
    return {
        runner(["ActivityName", activity_id]): activity_id
        for activity_id in ids
    }


def ensure_activity(name: str, runner=None) -> str:
    runner = runner or _qdbus
    existing = list_activities(runner)
    if name in existing:
        return existing[name]
    return runner(["CreateActivity", name]).strip()


def switch_activity(activity_id: str, runner=None) -> None:
    runner = runner or _qdbus
    runner(["SetCurrentActivity", activity_id])
```

```python
# src/rice/layouts.py
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
```

Create the three preset TOML files with the same zone values. They are documentation and installer defaults; the Python preset is the source used by tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_outputs.py tests/test_layouts.py tests/test_activities.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/outputs.py src/rice/activities.py src/rice/layouts.py defaults/layouts tests/test_outputs.py tests/test_layouts.py tests/test_activities.py
git commit -m "feat: detect outputs activities and layout presets"
```

---

### Task 4: Application Catalog and Installer Choices

**Files:**
- Create: `defaults/apps.toml`
- Create: `src/rice/apps.py`
- Test: `tests/test_apps.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_catalog(path: Path) -> dict`; `resolve_choices(catalog: dict, choices: dict) -> dict`; `app_commands(apps: dict) -> dict[str, list[str]]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_apps.py
from rice.apps import resolve_choices

CATALOG = {
    "work_browser": {
        "chrome": {"package": "google-chrome", "command": ["google-chrome-stable"], "wm_class": "google-chrome"},
        "firefox": {"package": "firefox", "command": ["firefox"], "wm_class": "firefox"},
    },
    "private_browser": {
        "brave": {"package": "brave-bin", "command": ["brave"], "wm_class": "brave-browser"},
        "chromium": {"package": "chromium", "command": ["chromium"], "wm_class": "chromium"},
    },
    "toggles": {
        "youtube_music": {"package": "youtube-music-bin", "command": ["youtube-music"], "wm_class": "com.github.th-ch.youtube-music"},
    },
}


def test_resolve_choices_selects_requested_variants():
    apps = resolve_choices(CATALOG, {"work_browser": "firefox", "private_browser": "chromium", "youtube_music": True})
    assert apps["work-browser"]["command"] == ["firefox"]
    assert apps["private-browser"]["command"] == ["chromium"]
    assert "youtube-music" in apps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_apps.py -v`  
Expected: FAIL because `rice.apps` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/apps.py
from pathlib import Path

import tomllib

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
```

Create `defaults/apps.toml` with generic entries for Chrome, Firefox, Brave, Chromium, Claude Desktop, Claude Code, Alacritty, Kitty, YouTube Music, Steam, Discord, OpenCode, and GPU recorder. No DSH, VPS, or personal URLs.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_apps.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add defaults/apps.toml src/rice/apps.py tests/test_apps.py
git commit -m "feat: add app catalog and choice resolver"
```

---

### Task 5: KWin Placement Generator

**Files:**
- Create: `templates/kwin/main.js.in`
- Modify: `src/rice/generate.py`
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: config, zones, outputs.
- Produces: `generate_kwin(config: dict) -> str`; `kwin_rules(config: dict) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generate.py
from rice.generate import generate_kwin, kwin_rules

CONFIG = {
    "output": [{"id": "main", "connector": "DP-1", "primary": True, "x": 0, "y": 0, "width": 5120, "height": 1440}],
    "zone": [{"id": "center-left", "output": "main", "kind": "app",
              "x": 0.0, "y": 0.0, "w": 0.5, "h": 1.0, "gap_px": 8}],
    "app": [{"id": "browser", "command": ["firefox"], "wm_class": "firefox"}],
    "placement": [{"app": "browser", "activity": "private", "zone": "center-left", "mode": "normal"}],
    "activities": {"private": {"name": "Private", "kde_id": "private-uuid"},
                   "work": {"name": "Work", "kde_id": "work-uuid"}},
}


def test_rules_resolve_zone_and_activity():
    rules = kwin_rules(CONFIG)
    assert rules[0]["wm_class"] == "firefox"
    assert rules[0]["output"] == "DP-1"
    assert rules[0]["activity"] == "private-uuid"
    assert rules[0]["zone"]["w"] == 0.5


def test_generated_js_contains_rules():
    js = generate_kwin(CONFIG)
    assert "const RULES =" in js
    assert "firefox" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_generate.py -v`  
Expected: FAIL because `rice.generate` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/generate.py
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "kwin" / "main.js.in"


def _zone(config, zone_id):
    zone = next(item for item in config["zone"] if item["id"] == zone_id)
    output = next(item for item in config["output"] if item["id"] == zone["output"])
    return {
        "output": output["connector"],
        "zone": {key: zone[key] for key in ("x", "y", "w", "h", "gap_px")},
    }


def kwin_rules(config: dict) -> list[dict]:
    apps = {app["id"]: app for app in config["app"]}
    activities = {role: data["kde_id"] for role, data in config["activities"].items()}
    rules = []
    for placement in config["placement"]:
        app = apps[placement["app"]]
        resolved = _zone(config, placement["zone"])
        rules.append({
            "wm_class": app.get("wm_class", "").lower(),
            "match_title": placement.get("match_title", "").lower(),
            "activity": activities.get(placement["activity"], ""),
            "mode": placement["mode"],
            "priority": placement.get("priority", 0),
            **resolved,
        })
    return sorted(rules, key=lambda item: item["priority"], reverse=True)


def generate_kwin(config: dict) -> str:
    rules = kwin_rules(config)
    return TEMPLATE.read_text().replace("__RULES__", json.dumps(rules, indent=2))
```

Create `templates/kwin/main.js.in` with actual KWin JavaScript:

```javascript
const RULES = __RULES__;

function outputByName(name) {
    const screens = workspace.screens;
    for (let i = 0; i < screens.length; i++) {
        if (screens[i].name === name) return screens[i];
    }
    return null;
}

function areaFor(output) {
    return workspace.clientArea(KWin.MaximizeArea, output, workspace.currentDesktop);
}

function currentActivityMatches(rule) {
    return !rule.activity || workspace.currentActivity === rule.activity;
}

function matchingRule(win) {
    const cls = (win.resourceClass || "").toLowerCase();
    const title = (win.caption || "").toLowerCase();
    for (const rule of RULES) {
        if (!currentActivityMatches(rule)) continue;
        if (rule.wm_class && rule.wm_class !== cls) continue;
        if (rule.match_title && title.indexOf(rule.match_title) < 0) continue;
        if (!rule.wm_class && !rule.match_title) continue;
        return rule;
    }
    return null;
}

function place(win, rule) {
    const output = outputByName(rule.output);
    if (!output) return;
    const area = areaFor(output);
    const gap = rule.zone.gap_px || 0;
    const x = Math.round(area.x + area.width * rule.zone.x + gap);
    const y = Math.round(area.y + area.height * rule.zone.y + gap);
    const w = Math.max(200, Math.round(area.width * rule.zone.w - gap * 2));
    const h = Math.max(200, Math.round(area.height * rule.zone.h - gap * 2));

    if (win.fullScreen) win.fullScreen = false;
    if (win.maximizeMode !== 0) win.setMaximize(false, false);
    workspace.sendClientToScreen(win, output);
    win.frameGeometry = { x: x, y: y, width: w, height: h };
    if (rule.mode === "maximized") {
        win.setMaximize(true, true);
    } else if (rule.mode === "fullscreen") {
        win.fullScreen = true;
    }
}

function applyRule(win) {
    if (!win.normalWindow || win._riceDone) return;
    const rule = matchingRule(win);
    if (rule) {
        place(win, rule);
        win._riceDone = true;
    }
}

workspace.windowAdded.connect(applyRule);
workspace.windowActivated.connect(applyRule);
const existing = workspace.windowList();
for (let i = 0; i < existing.length; i++) applyRule(existing[i]);
```

- [ ] **Step 4: Run test and syntax check**

Run: `python3 -m pytest tests/test_generate.py -v`  
Run: `python3 - <<'PY'` to write generated JS to a temp file and `node --check` it; skip if node is absent.  
Expected: PASS and JS syntax OK.

- [ ] **Step 5: Commit**

```bash
git add src/rice/generate.py templates/kwin/main.js.in tests/test_generate.py
git commit -m "feat: generate kwin placement script"
```

---

### Task 6: Noctalia, systemd, and Runtime Generators

**Files:**
- Create: `templates/noctalia/rice.toml.in`
- Create: `templates/systemd/rice-daemon.service.in`
- Create: `templates/systemd/rice-startup.service.in`
- Create: `templates/systemd/rice-fullscreen-watch.service.in`
- Create: `templates/systemd/rice-theme-boot.service.in`
- Create: `templates/systemd/rice-theme-hourly.service.in`
- Create: `templates/systemd/rice-theme-hourly.timer.in`
- Modify: `src/rice/generate.py`
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: config, paths.
- Produces: `generate_noctalia(config: dict) -> str`; `generate_systemd(config: dict, install_root: Path) -> dict[Path, str]`; `generate_runtime(config: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generate.py
import tomllib
from pathlib import Path

from rice.generate import generate_noctalia, generate_runtime, generate_systemd


def test_noctalia_output_is_valid_toml():
    text = generate_noctalia(CONFIG)
    data = tomllib.loads(text)
    assert "desktop_widgets" in data


def test_runtime_contains_startup_and_zones():
    data = generate_runtime(CONFIG)
    assert data["startup"]["private"] == ["browser"]
    assert data["zones"]["center-left"]["w"] == 0.5


def test_systemd_units_have_user_exec(tmp_path: Path):
    units = generate_systemd(CONFIG, tmp_path)
    content = "\n".join(units.values())
    assert "rice startup" in content
    assert "rice daemon" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_generate.py -v`  
Expected: FAIL because functions do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/rice/generate.py
import tomli_w


def generate_noctalia(config: dict) -> str:
    widgets = []
    for widget in config.get("desktop_widget", []):
        zone = next(item for item in config["zone"] if item["id"] == widget["zone"])
        output = next(item for item in config["output"] if item["id"] == zone["output"])
        widgets.append({
            "type": widget["plugin"],
            "output": output["connector"],
            "cx": round(output.get("x", 0) + output.get("width", 0) * (zone["x"] + zone["w"] / 2), 1),
            "cy": round(output.get("y", 0) + output.get("height", 0) * (zone["y"] + zone["h"] / 2), 1),
            "scale": widget.get("scale", 1.0),
        })
    data = {
        "desktop_widgets": {
            "enabled": True,
            "widget_order": [f"rice_{i}" for i in range(len(widgets))],
            "widget": {},
        }
    }
    for index, widget in enumerate(widgets):
        data["desktop_widgets"]["widget"][f"rice_{index}"] = widget
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
    templates = install_root / "templates" / "systemd"
    mapping = {
        "rice-daemon.service": "rice daemon",
        "rice-startup.service": "rice startup",
        "rice-fullscreen-watch.service": "rice daemon",
        "rice-theme-boot.service": "rice theme boot",
        "rice-theme-hourly.service": "rice theme hourly",
        "rice-theme-hourly.timer": "",
    }
    result = {}
    for filename, command in mapping.items():
        text = (templates / f"{filename}.in").read_text()
        result[Path(filename)] = text.replace("@RICE_COMMAND@", command)
    return result
```

Create actual unit templates. Example `rice-startup.service.in`:

```ini
[Unit]
Description=Rice startup applications
After=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.local/bin/@RICE_COMMAND@
RemainAfterExit=yes

[Install]
WantedBy=graphical-session.target
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_generate.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/generate.py templates/noctalia templates/systemd tests/test_generate.py
git commit -m "feat: generate noctalia and systemd artifacts"
```

---

### Task 7: Apply Pipeline and Backups

**Files:**
- Create: `src/rice/apply.py`
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: `load_config`, `validate_config`, generators, paths.
- Produces: `ApplyResult(changed: list[Path], skipped: list[str])`; `apply_config(config_path: Path, dry_run: bool = False, runner=None) -> ApplyResult`; `backup_paths(paths: list[Path]) -> Path`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_apply.py
from pathlib import Path

from rice.apply import apply_config


def test_apply_writes_generated_files_and_backs_up(tmp_path, monkeypatch):
    config = tmp_path / "rice.toml"
    config.write_text((Path("defaults/rice.toml")).read_text())
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local/state"))
    result = apply_config(config, runner=lambda *args, **kwargs: None)
    assert any("main.js" in str(path) for path in result.changed)
    assert (home / ".config/noctalia/rice.toml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_apply.py -v`  
Expected: FAIL because `rice.apply` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/apply.py
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import load_config, save_config, validate_config
from .generate import generate_kwin, generate_noctalia, generate_runtime, generate_systemd
from .paths import config_home, data_home, state_home


@dataclass
class ApplyResult:
    changed: list[Path]
    skipped: list[str]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def backup_paths(paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = state_home() / "rice" / "backups" / stamp
    root.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.is_file():
            target = root / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return root


def apply_config(config_path: Path, dry_run: bool = False, runner=None) -> ApplyResult:
    config = load_config(config_path)
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))

    kwin_dir = data_home() / "kwin/scripts/rice-placement"
    noir_dir = config_home() / "noctalia"
    unit_dir = config_home() / "systemd/user"
    runtime_path = state_home() / "rice/runtime.json"
    generated = {
        kwin_dir / "contents/code/main.js": generate_kwin(config),
        kwin_dir / "metadata.json": __import__("json").dumps({
            "KPlugin": {"Name": "Rice Placement", "Version": "0.1.0"},
            "X-Plasma-API": "javascript",
        }, indent=2),
        noir_dir / "rice.toml": generate_noctalia(config),
        runtime_path: __import__("json").dumps(generate_runtime(config), indent=2),
    }
    for name, content in generate_systemd(config, Path(__file__).resolve().parents[2]).items():
        generated[unit_dir / name] = content

    if dry_run:
        return ApplyResult(list(generated), [])

    backup_paths(list(generated))
    for path, content in generated.items():
        _write(path, content)
    if runner is not None:
        runner("systemctl", "--user", "daemon-reload")
        runner("qdbus6", "org.kde.KWin", "/KWin", "reconfigure")
        runner("noctalia", "msg", "config-reload")
    return ApplyResult(list(generated), [])
```

The actual implementation must write the KWin metadata file, add `#!/usr/bin/env python3` wrappers, and use `runner` for command execution. The test injects a no-op runner.

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_apply.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/apply.py tests/test_apply.py
git commit -m "feat: apply generated rice configuration"
```

---

### Task 8: Startup and Activity Autostart

**Files:**
- Create: `src/rice/startup.py`
- Test: `tests/test_startup.py`

**Interfaces:**
- Consumes: runtime config, `$XDG_RUNTIME_DIR`.
- Produces: `run_startup(runtime: dict, launcher=...) -> list[str]`; `run_autostart(runtime: dict, role: str, launcher=...) -> list[str]`; `clear_session_markers() -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_startup.py
from rice.startup import run_autostart, run_startup

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_startup.py -v`  
Expected: FAIL because `rice.startup` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/startup.py
import os
import subprocess
from pathlib import Path


def _runtime_root() -> Path:
    root = Path(os.environ["XDG_RUNTIME_DIR"]) / "rice"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_launcher(command: list[str]):
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def _launch(runtime: dict, app_ids: list[str], launcher):
    launched = []
    for app_id in app_ids:
        app = runtime["apps"][app_id]
        launcher(app["command"])
        launched.append(app["command"])
    return launched


def run_startup(runtime: dict, launcher=_default_launcher) -> list[str]:
    launched = []
    launched.extend(_launch(runtime, runtime.get("startup", {}).get("always", []), launcher))
    launched.extend(_launch(runtime, runtime.get("startup", {}).get("private", []), launcher))
    (_runtime_root() / "startup.done").write_text("1")
    return launched


def run_autostart(runtime: dict, role: str, launcher=_default_launcher) -> list[str]:
    marker = _runtime_root() / f"autostart-{role}.done"
    if marker.exists():
        return []
    app_ids = runtime.get("autostart", {}).get(role, {}).get("apps", [])
    launched = _launch(runtime, app_ids, launcher)
    marker.write_text("1")
    return launched


def clear_session_markers() -> None:
    for marker in _runtime_root().glob("*.done"):
        marker.unlink()
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_startup.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/startup.py tests/test_startup.py
git commit -m "feat: add startup and autostart resolver"
```

---

### Task 9: D-Bus Daemon and CLI Commands

**Files:**
- Create: `src/rice/daemon.py`
- Modify: `src/rice/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: runtime config, startup functions, theme functions.
- Produces: D-Bus `org.rice.Rice` methods `SwitchActivity(role)`, `RunStartup()`, `ThemeNext()`, `ThemePrevious()`, `MediaToggle()`, `MediaNext()`, `MediaPrevious()`; CLI commands `startup`, `activity`, `daemon`, `apply`, `doctor`, `theme`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
def test_cli_has_core_commands():
    result = run_cli("--help")
    assert result.returncode == 0
    for command in ("apply", "startup", "activity", "daemon", "doctor"):
        assert command in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::test_cli_has_core_commands -v`  
Expected: FAIL because the commands are not registered.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/daemon.py
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

from .activities import switch_activity
from .startup import run_autostart, run_startup
from .theme import next_theme, previous_theme


class RiceDaemon(dbus.service.Object):
    def __init__(self, bus, runtime):
        super().__init__(bus, "/Rice")
        self.runtime = runtime

    @dbus.service.method("org.rice.Rice", in_signature="s", out_signature="")
    def SwitchActivity(self, role):
        role = str(role)
        switch_activity(self.runtime["activities"][role]["kde_id"])
        run_autostart(self.runtime, role)

    @dbus.service.method("org.rice.Rice", out_signature="")
    def RunStartup(self):
        run_startup(self.runtime)

    @dbus.service.method("org.rice.Rice", out_signature="")
    def ThemeNext(self):
        next_theme(self.runtime)

    @dbus.service.method("org.rice.Rice", out_signature="")
    def ThemePrevious(self):
        previous_theme(self.runtime)


def load_runtime():
    from .paths import state_home
    return __import__("json").loads((state_home() / "rice/runtime.json").read_text())


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("org.rice.Rice", bus)
    runtime = load_runtime()
    RiceDaemon(bus, runtime)
    GLib.MainLoop().run()
```

Add CLI subcommands with `argparse`:

```python
# src/rice/cli.py
import argparse
import json
from pathlib import Path

from .apply import apply_config
from .config import config_path
from .paths import state_home
from .startup import run_startup


def run_apply(args):
    return apply_config(config_path(), dry_run=args.dry_run)


def _runtime():
    return json.loads((state_home() / "rice/runtime.json").read_text())


def run_startup_command(args):
    run_startup(_runtime())
    return 0


def run_activity_command(args):
    from .activities import switch_activity
    runtime = _runtime()
    switch_activity(runtime["activities"][args.role]["kde_id"])
    from .startup import run_autostart
    run_autostart(runtime, args.role)
    return 0


def run_theme_command(args):
    from .theme import next_theme, previous_theme
    (next_theme if args.value == "next" else previous_theme)(_runtime())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rice")
    parser.add_argument("--version", action="version", version="rice 0.1.0")
    sub = parser.add_subparsers(dest="command")

    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.set_defaults(func=run_apply)

    startup_parser = sub.add_parser("startup")
    startup_parser.set_defaults(func=run_startup_command)

    daemon_parser = sub.add_parser("daemon")
    daemon_parser.set_defaults(func=lambda args: __import__("rice.daemon", fromlist=["main"]).main())
    sub.add_parser("doctor").set_defaults(func=lambda args: 0)

    activity_parser = sub.add_parser("activity")
    activity_parser.add_argument("role", choices=["private", "work"])
    activity_parser.set_defaults(func=run_activity_command)

    theme_parser = sub.add_parser("theme")
    theme_parser.add_argument("value", choices=["next", "previous"])
    theme_parser.set_defaults(func=run_theme_command)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args) or 0
```

Add `rice daemon` to call `daemon.main()` and `rice activity` to call the KDE Activity Manager followed by the D-Bus autostart method. The daemon must load the generated runtime JSON from `$XDG_STATE_HOME/rice/runtime.json`.

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_cli.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/daemon.py src/rice/cli.py tests/test_cli.py
git commit -m "feat: add daemon and core cli commands"
```

---

### Task 10: Theme Engine and Asset Manifest

**Files:**
- Create: `src/rice/theme.py`
- Create: `assets/wallpapers/manifest.toml`
- Create: `tests/test_theme.py`
- Create: `tests/test_pii.py`

**Interfaces:**
- Consumes: config theme section, wallpaper directory.
- Produces: `list_wallpapers(directory: Path) -> list[Path]`; `next_theme(runtime: dict) -> Path`; `previous_theme(runtime: dict) -> Path`; `wallpaper_status(directory: Path) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_theme.py
from pathlib import Path

from rice.theme import list_wallpapers, wallpaper_status


def test_list_wallpapers_filters_images(tmp_path: Path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    assert [path.name for path in list_wallpapers(tmp_path)] == ["a.png", "b.jpg"]


def test_wallpaper_status_counts_missing(tmp_path: Path):
    status = wallpaper_status(tmp_path)
    assert status["count"] == 0
    assert status["directory"] == str(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_theme.py -v`  
Expected: FAIL because `rice.theme` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/theme.py
from pathlib import Path

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}


def list_wallpapers(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED
    )


def wallpaper_status(directory: Path) -> dict:
    files = list_wallpapers(directory)
    return {"directory": str(directory), "count": len(files), "files": [path.name for path in files]}


def _current(runtime: dict) -> Path | None:
    from .paths import state_home
    marker = state_home() / "rice/theme-current"
    return Path(marker.read_text()) if marker.exists() else None


def _apply(runtime: dict, path: Path, runner=None):
    import subprocess
    from .paths import state_home
    outputs = runtime.get("theme", {}).get("outputs", [])
    if not outputs:
        raise ValueError("theme.outputs is empty")
    command = ["noctalia", "msg", "wallpaper-set"]
    for output in outputs:
        (runner or subprocess.run)([*command, output, str(path)], check=True)
    marker = state_home() / "rice/theme-current"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(path))


def next_theme(runtime: dict, runner=None) -> Path:
    directory = Path(runtime["theme"]["wallpaper_dir"]).expanduser()
    files = list_wallpapers(directory)
    if not files:
        raise FileNotFoundError(directory)
    current = _current(runtime)
    index = files.index(current) + 1 if current in files else 0
    target = files[index % len(files)]
    _apply(runtime, target, runner)
    return target


def previous_theme(runtime: dict, runner=None) -> Path:
    directory = Path(runtime["theme"]["wallpaper_dir"]).expanduser()
    files = list_wallpapers(directory)
    if not files:
        raise FileNotFoundError(directory)
    current = _current(runtime)
    index = files.index(current) - 1 if current in files else 0
    target = files[index % len(files)]
    _apply(runtime, target, runner)
    return target
```

Implement theme rotation by reading and writing
`$XDG_STATE_HOME/rice/theme-current` and calling `noctalia msg wallpaper-set`
for each configured output. The runtime config supplies the output list and
`same_image_all_outputs`. Add a manifest with generic source links and no
personal data:

```toml
# assets/wallpapers/manifest.toml
[[wallpaper]]
id = "example"
file = "example.png"
source = "https://example.invalid/source"
artist = "Example Artist"
license = "private-personal-use-only"
sha256 = ""
```

```python
# tests/test_pii.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"/home/[A-Za-z0-9._-]+"),
    re.compile(r"(?<!127\.0\.0\.1)\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\."),
    re.compile(r"tailscale", re.IGNORECASE),
    re.compile(r"(?:^|\s)ssh\s", re.IGNORECASE),
    re.compile(r"\bvps\b", re.IGNORECASE),
]


def test_no_personal_data_in_committed_files():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.name == "test_pii.py" or "docs/superpowers" in str(path) or "assets/wallpapers" in str(path):
            continue
        if path.suffix not in {".md", ".py", ".toml", ".sh", ".js", ".in"}:
            continue
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    assert not hits, "personal data candidates: " + ", ".join(hits)
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_theme.py tests/test_pii.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rice/theme.py assets/wallpapers/manifest.toml tests/test_theme.py tests/test_pii.py
git commit -m "feat: add theme engine and asset manifest"
```

---

### Task 11: Installer and Uninstaller

**Files:**
- Create: `install.sh`
- Create: `uninstall.sh`
- Create: `src/rice/installer.py`
- Test: `tests/test_installer.py`

**Interfaces:**
- Consumes: config, defaults, generators, apply, apps.
- Produces: `Installer.run(choices: dict, dry_run: bool = False) -> None`; `install.sh` bootstrap; `uninstall.sh` wrapper.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_installer.py
from rice.installer import package_plan

CHOICES = {"work_browser": "firefox", "private_browser": "chromium", "youtube_music": False}


def test_package_plan_includes_selected_variants():
    packages = package_plan(CHOICES)
    assert "firefox" in packages
    assert "chromium" in packages
    assert "youtube-music-bin" not in packages


def test_package_plan_has_no_personal_entries():
    packages = package_plan(CHOICES)
    assert all("dsh" not in package and "tailscale" not in package for package in packages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_installer.py -v`  
Expected: FAIL because `rice.installer` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# src/rice/installer.py
import shutil
import subprocess
from pathlib import Path

from .apps import load_catalog, resolve_choices
from .apply import apply_config
from .config import save_config, validate_config
from .paths import config_path, data_home


def package_plan(choices: dict) -> list[str]:
    catalog = load_catalog(Path(__file__).resolve().parents[2] / "defaults/apps.toml")
    apps = resolve_choices(catalog, choices)
    packages = ["python", "python-tomli-w", "python-dbus", "python-gobject", "noctalia", "kscreen"]
    for app in apps.values():
        package = app.get("package")
        if package and package not in packages:
            packages.append(package)
    return packages


def _run(command, dry_run=False):
    if dry_run:
        print("DRY-RUN:", " ".join(command))
        return
    subprocess.run(command, check=True)


def install_packages(packages: list[str], aur_helper: str, dry_run=False):
    official = [package for package in packages if package not in {"noctalia", "gpu-screen-recorder-ui", "youtube-music-bin", "brave-bin", "google-chrome"}]
    aur = [package for package in packages if package not in official]
    if official:
        _run(["sudo", "pacman", "-S", "--needed", "--noconfirm", *official], dry_run)
    if aur:
        _run([aur_helper, "-S", "--needed", "--noconfirm", *aur], dry_run)


def install_tree(repo: Path, data_dir: Path, bin_dir: Path, dry_run=False):
    install_root = data_dir / "rice"
    if dry_run:
        print("DRY-RUN: install", repo, "to", install_root)
        return install_root
    install_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / "src/rice", install_root / "src/rice", dirs_exist_ok=True)
    shutil.copytree(repo / "templates", install_root / "templates", dirs_exist_ok=True)
    shutil.copytree(repo / "defaults", install_root / "defaults", dirs_exist_ok=True)
    for plugin in (repo / "plugins").iterdir():
        if plugin.is_dir():
            shutil.copytree(plugin, data_dir / "noctalia-plugins" / plugin.name, dirs_exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "rice"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "export PYTHONPATH=\"$HOME/.local/share/rice/src${PYTHONPATH:+:$PYTHONPATH}\"\n"
        "exec python3 -m rice.cli \"$@\"\n"
    )
    wrapper.chmod(0o755)
    return install_root


def build_initial_config(choices: dict) -> dict:
    from copy import deepcopy
    from .config import load_config
    from .layouts import choose_layout, layout_config
    from .activities import ensure_activity, list_activities
    from .outputs import detect_outputs
    base = load_config(Path(__file__).resolve().parents[2] / "defaults/rice.toml")
    catalog = load_catalog(Path(__file__).resolve().parents[2] / "defaults/apps.toml")
    apps = resolve_choices(catalog, choices)
    base["app"] = [{"id": app_id, **entry} for app_id, entry in apps.items()]
    outputs = detect_outputs()
    base["output"] = [
        {"id": output.id, "role": output.id, "connector": output.connector,
         "primary": output.primary, "x": output.x, "y": output.y,
         "width": output.width, "height": output.height}
        for output in outputs
    ]
    base.update(layout_config(choose_layout(outputs), outputs))
    known = list_activities()
    for role, name in (("private", "Private"), ("work", "Work")):
        base["activities"][role]["kde_id"] = known.get(name) or ensure_activity(name)
    return base


class Installer:
    def run(self, choices: dict, dry_run: bool = False):
        packages = package_plan(choices)
        helper = shutil.which("paru") or shutil.which("yay")
        if not helper:
            raise RuntimeError("No AUR helper found. Install paru or yay first.")
        install_packages(packages, helper, dry_run)
        repo = Path(__file__).resolve().parents[2]
        install_tree(repo, data_home(), Path.home() / ".local/bin", dry_run)
        config = build_initial_config(choices)
        errors = validate_config(config)
        if errors:
            raise ValueError("; ".join(errors))
        if dry_run:
            print("DRY-RUN: write", config_path())
            return
        save_config(config_path(), config)
        apply_config(config_path())
```

Create `install.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m rice.installer "$@"
```

`uninstall.sh` calls `rice uninstall`, disables only units whose names start
with `rice-`, removes the generated KWin script, and restores the latest backup.
The installer must verify `/etc/os-release` contains `arch` or `cachyos`,
`plasmashell --version`, `noctalia --version`, and that a graphical session
exists before touching files.

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_installer.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add install.sh uninstall.sh src/rice/installer.py tests/test_installer.py
git commit -m "feat: add installer and package planning"
```

---

### Task 12: Documentation, Integration Test, and Public Repository Hygiene

**Files:**
- Create: `README.md`
- Create: `docs/INSTALL.md`
- Create: `docs/CONFIGURATION.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/PLACEMENT.md`
- Create: `docs/STARTUP.md`
- Create: `docs/THEMING.md`
- Create: `docs/ASSETS.md`
- Create: `docs/TROUBLESHOOTING.md`
- Create: `tests/test_integration.py`
- Modify: `tests/test_pii.py`

**Interfaces:**
- Consumes: all core modules.
- Produces: public documentation, dry-run integration coverage, PII gate.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_integration.py
from pathlib import Path

from rice.apply import apply_config


def test_dry_run_lists_generated_paths(tmp_path, monkeypatch):
    config = Path("defaults/rice.toml")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    result = apply_config(config, dry_run=True)
    assert any("main.js" in str(path) for path in result.changed)
    assert not (tmp_path / "data").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_integration.py -v`  
Expected: FAIL until `apply_config` dry-run returns all generated paths and does not write.

- [ ] **Step 3: Write minimal documentation**

Create English README sections:

```markdown
# Bleach Work/Private Rice Balance

A configurable KDE Plasma 6 and Noctalia rice for Arch-based systems.

## What It Does

- Work and private application sets
- Configurable output roles and tiling zones
- Triple-monitor and ultrawide presets
- Generated KWin, Noctalia, and systemd configuration
- No bundled third-party wallpapers

## Requirements

Arch Linux or CachyOS, KDE Plasma 6, KWin, Noctalia 5.5+, and paru or yay.

## Install

```bash
git clone <repository-url>
cd diononline-bleach-work-rice-balance
./install.sh
```

## Privacy

The repository contains no personal hosts, VPS endpoints, Tailscale names, or
wallpaper binaries.
```

Create the other docs with the sections named in the spec: install prerequisites,
config reference, generated artifact flow, placement and zones, startup versus
autostart, theme and wallpaper policy, asset attribution, and troubleshooting.
Docs must not contain literal `/home/` paths or personal URLs.

- [ ] **Step 4: Run all checks**

Run: `python3 -m pytest -v`  
Run: `python3 -m compileall -q src`  
Run: `bash -n install.sh uninstall.sh bin/rice`  
Run: `python3 -m pytest tests/test_pii.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md docs tests/test_integration.py tests/test_pii.py
git commit -m "docs: add installation and configuration documentation"
```

---

## Plan Self-Review

- Spec coverage: core config, outputs, zones, layouts, activities, app choices, KWin generation, Noctalia/systemd generation, apply/backups, startup/autostart, daemon, theme, installer, docs, PII, and tests all have tasks.
- Configurator is intentionally excluded and requires a separate plan per the spec phase split.
- No copyrighted wallpaper binaries, personal links, or system-wide login changes are included.
- Interfaces use `rice.` modules and the same config keys across tasks.
- The plan contains no TBD or placeholder implementation steps.
