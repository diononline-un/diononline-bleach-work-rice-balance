# Local Web Configurator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a localhost-only web configurator for `rice.toml` with output-role mapping, a draggable/resizable zone canvas, structured app/placement/startup/autostart/widget/theme editing, validation, backups, restore, and the same apply path as the CLI.

**Architecture:** A standard-library Python HTTP server (`src/rice/web.py`) binds `127.0.0.1`, creates a random bearer token, serves `src/web/` static assets, and exposes a small JSON API. The browser keeps the config document in memory, edits zones on a per-output canvas, and sends a complete TOML-equivalent JSON document to the backend for validation and atomic TOML writes. Apply calls the existing `rice.apply.apply_config` path.

**Tech Stack:** Python 3.11+, standard library HTTP server, `tomli-w`, vanilla HTML/CSS/JS canvas interactions, pytest, Node for JS syntax checks.

**Spec:** `docs/superpowers/specs/2026-11-15-core-design.md` (§7, §13, §17 Phase 2)

## Global Constraints

- Localhost only: bind `127.0.0.1`, never `0.0.0.0`.
- Per-session bearer token on all mutating requests.
- No personal paths/hosts/VPS/Tailscale/credentials; no wallpaper binaries.
- English UI and documentation.
- Config writes are complete-document, validated, atomic, and backed up.
- No arbitrary command execution through the API or configurator.
- `rice.toml` remains canonical; apply runs the existing CLI pipeline.
- Every task ends with passing tests and a commit.

---

## File Structure

```text
bin/rice-config
src/rice/web.py
src/web/index.html
src/web/style.css
src/web/app.js
tests/test_web.py
tests/test_web_assets.py
docs/CONFIGURATOR.md
src/rice/cli.py
src/rice/installer.py
install.sh
uninstall.sh
README.md
PROJECT_STATUS.md
CHANGELOG.md
```

### Task 1: Backend Server and API

**Files:**
- Create: `src/rice/web.py`
- Create: `bin/rice-config`
- Modify: `src/rice/cli.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `load_config`, `save_config`, `validate_config`, `config_path`, `apply_config`, `detect_outputs`, `apps.load_catalog`, `paths.state_home`.
- Produces: `make_server(config_path: Path, token: str, apply_func=None, host="127.0.0.1", port=0) -> ThreadingHTTPServer`; `run_server(open_browser=True) -> int`; endpoints in the spec.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_web.py
import http.client
import json
import threading
from pathlib import Path

import pytest

from rice.config import load_config, save_config
from rice.web import make_server

TOKEN = "test-token"


@pytest.fixture()
def server(tmp_path):
    path = tmp_path / "rice.toml"
    save_config(path, load_config(Path("defaults/rice.toml")))
    httpd = make_server(path, TOKEN, apply_func=lambda *a, **k: None)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, path
    httpd.shutdown()
    httpd.server_close()


def request(httpd, method, path, body=None, token=TOKEN):
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    payload = None if body is None else json.dumps(body)
    conn.request(method, path, body=payload, headers=headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def test_health(server):
    status, body = request(server[0], "GET", "/api/health", token=None)
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_mutations_require_bearer(server):
    status, _ = request(server[0], "PUT", "/api/config", {"config": {}}, token=None)
    assert status == 401


def test_state_contains_config_and_validation(server):
    status, body = request(server[0], "GET", "/api/state")
    state = json.loads(body)
    assert status == 200
    assert "config" in state
    assert "validation" in state
    assert state["validation"] == []


def test_put_config_validates_and_writes(server):
    httpd, path = server
    config = load_config(path)
    config["meta"]["profile_name"] = "edited"
    status, body = request(httpd, "PUT", "/api/config", {"config": config})
    assert status == 200
    assert load_config(path)["meta"]["profile_name"] == "edited"


def test_put_config_rejects_invalid_document(server):
    httpd, path = server
    before = load_config(path)
    config = load_config(path)
    config["placement"][0]["zone"] = "missing"
    status, body = request(httpd, "PUT", "/api/config", {"config": config})
    assert status == 400
    assert "unknown zone" in body.decode()
    assert load_config(path) == before


def test_apply_uses_injected_apply_func(server):
    httpd, path = server
    calls = []
    httpd.apply_func = lambda config_path, dry_run=False: calls.append((config_path, dry_run))
    status, _ = request(httpd, "POST", "/api/apply", {})
    assert status == 200
    assert calls == [(path, False)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_web.py -v`  
Expected: FAIL because `rice.web` does not exist.

- [ ] **Step 3: Implement the server**

Create `src/rice/web.py` with:

```python
from __future__ import annotations

import json
import secrets
import shutil
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .apply import apply_config
from .apps import load_catalog
from .config import load_config, save_config, validate_config
from .outputs import detect_outputs
from .paths import config_path, state_home

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
BACKUP_ROOT = state_home() / "rice" / "web-backups"


class RiceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, config_path: Path, token: str, apply_func=None):
        super().__init__(address, handler)
        self.config_path = Path(config_path)
        self.token = token
        self.apply_func = apply_func or apply_config
```

Implement a `BaseHTTPRequestHandler` with:

- `GET /api/health` -> `{"status": "ok"}`.
- `GET /api/state` -> `{"config": ..., "validation": validate_config(config), "outputs": [ ... ]}`.
- `GET /api/outputs` -> detected outputs as JSON-safe dicts.
- `PUT /api/config` -> require `Authorization: Bearer <token>`; read JSON `{"config": ...}`; validate; save with `save_config`.
- `POST /api/validate` -> require token; return `{"errors": [...]}`.
- `POST /api/apply` -> require token; validate current file; call `server.apply_func(server.config_path, dry_run=False)`.
- `POST /api/backup` -> require token; copy current config to `BACKUP_ROOT/<YYYYMMDD-HHMMSS>/rice.toml`; return path.
- `POST /api/restore` -> require token; body `{"path": "<path>"}`; only allow a path under `BACKUP_ROOT`; validate; `save_config`.
- `GET /` -> `index.html`; `GET /app.js`, `/style.css` -> static.
- Return JSON errors with 400/401/404 and no tracebacks.

`make_server` constructs `RiceHTTPServer`, and `run_server` creates a token, prints `http://127.0.0.1:<port>/?token=...`, opens the browser, and serves until interrupted.

Add `rice config` CLI:

```python
def run_config(args):
    from .web import run_server
    return run_server(open_browser=not args.no_browser)
```

Add parser `config` with `--no-browser`, and create `bin/rice-config`:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m rice.web "$@"
```

`python3 -m rice.web` calls `run_server`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_web.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/rice/web.py src/rice/cli.py bin/rice-config tests/test_web.py
git commit -m "feat: add local configurator API"
git push -u origin feat/configurator
```

### Task 2: UI Shell, State Loading, and Tabs

**Files:**
- Create: `src/web/index.html`
- Create: `src/web/style.css`
- Create: `src/web/app.js`
- Test: `tests/test_web_assets.py`

**Interfaces:**
- Consumes: `/api/state`, `/api/validate`, `/api/config`, `/api/apply`.
- Produces: tabs Apps, Outputs, Layout, Placement, Startup, Autostart, Widgets, Theme, Apply; token from `?token=`; save/validate/apply buttons.

- [ ] **Step 1: Write the failing asset tests**

```python
# tests/test_web_assets.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ui_contains_all_tabs():
    text = (ROOT / "src/web/index.html").read_text(encoding="utf-8")
    for tab in ("Apps", "Outputs", "Layout", "Placement", "Startup", "Autostart", "Widgets", "Theme", "Apply"):
        assert f">{tab}<" in text


def test_ui_has_canvas_and_auth_client():
    js = (ROOT / "src/web/app.js").read_text(encoding="utf-8")
    assert "pointerdown" in js
    assert "Authorization" not in js or "sessionStorage" in js
    assert "getContext" in js or "canvas" in js
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_web_assets.py -v`  
Expected: FAIL because assets do not exist.

- [ ] **Step 3: Implement UI shell**

`index.html` contains:

```html
<div id="app">
  <nav id="tabs"></nav>
  <main id="panel"></main>
  <footer>
    <button id="validate">Validate</button>
    <button id="save">Save</button>
    <button id="apply">Apply</button>
    <span id="status"></span>
  </footer>
</div>
```

`style.css` uses a dark neutral theme, a responsive two-column layout, monospace JSON editors, and `.zone`/`.canvas` styles for the layout tab.

`app.js`:

- Read the token from `new URLSearchParams(location.search).get("token")`.
- Keep `state.config`, `state.selected`, `state.dirty`.
- `api(path, options)` adds `Authorization: Bearer <token>` and JSON headers.
- Load `/api/state` at startup.
- Render tabs and dispatch to renderers.
- `Validate` calls `/api/validate`; `Save` calls `PUT /api/config`; `Apply` calls `/api/apply`.
- Show a status line and disable Apply while a request is running.
- Do not use `eval` or inject untrusted HTML; use `textContent` for values.

- [ ] **Step 4: Run tests and JS syntax check**

Run: `.venv/bin/python -m pytest tests/test_web_assets.py -v`  
Run: `node --check src/web/app.js`  
Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/web tests/test_web_assets.py
git commit -m "feat: add configurator shell"
git push
```

### Task 3: Canvas Zone Editor

**Files:**
- Modify: `src/web/app.js`
- Modify: `src/web/style.css`
- Test: `tests/test_web_assets.py`

**Interfaces:**
- Consumes: `state.config.output`, `state.config.zone`.
- Produces: `renderLayout()`, `addZone(outputId)`, `removeZone(zoneId)`, `dragZone(event, zone, handle)`, `snap(value)`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_web_assets.py
def test_layout_editor_supports_drag_resize_add_and_remove():
    js = (ROOT / "src/web/app.js").read_text(encoding="utf-8")
    for token in ("pointerdown", "pointermove", "pointerup", "resize-zone", "add-zone", "remove-zone"):
        assert token in js


def test_zone_updates_stay_relative():
    js = (ROOT / "src/web/app.js").read_text(encoding="utf-8")
    assert "Math.min(1" in js
    assert "Math.max(0" in js
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_web_assets.py -k layout -v`  
Expected: FAIL.

- [ ] **Step 3: Implement canvas editor**

In `app.js`, implement:

```javascript
function snap(value) {
  return Math.round(value * 100) / 100;
}

function renderLayout() {
  const canonical = state.config.output;
  const main = canonical.find((output) => output.primary) || canonical[0];
  const zones = state.config.zone.filter((zone) => zone.output === main.id);
  // Render a .canvas container with aspect-ratio from main.width/main.height.
  // Each zone is a .zone absolutely positioned with x/w percentages.
  // Add a resize handle with class resize-zone at the bottom-right.
}
```

Use pointer events on the canvas:

- `pointerdown` on `.zone` records the zone id, start geometry, and pointer position.
- `pointerdown` on `.resize-zone` sets a resize flag.
- `pointermove` updates `zone.x/y/w/h` in normalized units; clamp to `[0,1]`; snap to 0.01; keep `x+w <= 1`, `y+h <= 1`; apply a minimum of 0.05.
- `pointerup` clears drag state and marks the document dirty.
- `add-zone` appends a zone with `id = "custom-<n>"`, `kind = "app"`, `x=0.1`, `y=0.1`, `w=0.3`, `h=0.3`, `gap_px=8`.
- `remove-zone` deletes the selected zone and any placement referring to it, with a confirmation.

Every edit mutates `state.config` only; nothing is sent until Save/Apply.

- [ ] **Step 4: Run tests and syntax check**

Run: `.venv/bin/python -m pytest tests/test_web_assets.py -v`  
Run: `node --check src/web/app.js`.

- [ ] **Step 5: Commit and push**

```bash
git add src/web/app.js src/web/style.css tests/test_web_assets.py
git commit -m "feat: add canvas zone editor"
git push
```

### Task 4: Structured Editors and Apply Workflow

**Files:**
- Modify: `src/web/app.js`
- Modify: `src/web/index.html`
- Modify: `src/web/style.css`
- Test: `tests/test_web_assets.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: config arrays `app`, `placement`, `startup`, `autostart`, `desktop_widget`, `theme`.
- Produces: editable forms/tables for each tab; dirty-state warning; validation summary; apply result.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_web_assets.py
def test_structured_tabs_have_forms():
    js = (ROOT / "src/web/app.js").read_text(encoding="utf-8")
    for token in ("renderApps", "renderPlacement", "renderStartup", "renderAutostart", "renderWidgets", "renderTheme"):
        assert token in js


def test_apply_warns_before_leaving_dirty_state():
    js = (ROOT / "src/web/app.js").read_text(encoding="utf-8")
    assert "beforeunload" in js
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_web_assets.py -k structured -v`  
Expected: FAIL.

- [ ] **Step 3: Implement editors**

- Apps: table with id, name, command (comma-separated argv), wm_class, activities.
- Placement: table of app, activity, zone, mode, priority; add/remove row.
- Startup: two lists for `always` and `private`, with checkboxes from app ids.
- Autostart: role sections Private/Work with app checkboxes.
- Widgets: table of id, plugin, zone, scale.
- Theme: text input wallpaper_dir, outputs multi-select, toggles same_image_all_outputs, rotation, pause flags.
- Outputs: role select per output; connector read-only; no hardcoded connectors.

Forms mutate `state.config`; validation only happens on Validate/Save/Apply.

- [ ] **Step 4: Implement apply UX**

- `Save` validates, PUTs config, updates state.
- `Apply` validates, PUTs config, then POSTs `/api/apply`; show errors in a panel.
- `beforeunload` warns when `state.dirty`.
- No automatic apply on input.

- [ ] **Step 5: Run tests**

Run full pytest and `node --check src/web/app.js`.

- [ ] **Step 6: Commit and push**

```bash
git add src/web tests/test_web.py tests/test_web_assets.py
git commit -m "feat: add configurator editors and apply flow"
git push
```

### Task 5: Packaging, Docs, Security, and PR

**Files:**
- Modify: `src/rice/installer.py`
- Modify: `src/rice/web.py`
- Modify: `README.md`
- Modify: `docs/INSTALL.md`
- Modify: `docs/ARCHITECTURE.md`
- Create: `docs/CONFIGURATOR.md`
- Modify: `PROJECT_STATUS.md`
- Modify: `CHANGELOG.md`
- Test: `tests/test_installer.py`
- Test: `tests/test_pii.py`

**Interfaces:**
- Consumes: all web assets and CLI.
- Produces: installed `rice-config`, web assets copied to `$XDG_DATA_HOME/rice/src/web`, docs, security checks, PR.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_installer.py
def test_install_tree_copies_web_assets(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    (repo / "src/web").mkdir(parents=True)
    (repo / "src/web/index.html").write_text("ok", encoding="utf-8")
    install_tree(repo, tmp_path / "data", tmp_path / "bin")
    assert (tmp_path / "data/rice/src/web/index.html").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_installer.py::test_install_tree_copies_web_assets -v`  
Expected: FAIL.

- [ ] **Step 3: Finish packaging and docs**

- `install_tree` copies `src/web`; installs `bin/rice-config`; wrapper points to `$XDG_DATA_HOME/rice/src`.
- `run_server` requires a token; docs state localhost-only and per-session token.
- PII scan includes web assets (`.js` already scanned).
- Add `docs/CONFIGURATOR.md` with screenshots-free usage, token behavior, API endpoints, backup/restore, security, and limitations.
- Update README and status/changelog; Plan 3 done.
- Do not add external JS dependencies.

- [ ] **Step 4: Run all checks**

Run full pytest, `node --check src/web/app.js`, `compileall`, `bash -n`, `git diff --check`, PII.

- [ ] **Step 5: Commit, push, open PR**

```bash
git add src/rice src/web bin/rice-config tests docs README.md PROJECT_STATUS.md CHANGELOG.md install.sh uninstall.sh
git commit -m "docs: document local configurator"
git push
gh pr create --fill
```

---

## Plan Self-Review

- Spec coverage: local HTTP server, token, tabs, canvas zones, app/placement/startup/autostart/widget/theme editors, validate/apply/backup/restore, docs, packaging, PII.
- Security: localhost only, bearer token, no command execution from config, complete-document validation.
- No personal paths, hosts, credentials, or wallpaper binaries.
- Each task has tests, a commit, and a push step.
- Interfaces use `make_server`, `/api/*`, `run_server`, and the existing `apply_config` consistently.
- No TBD or placeholder implementation steps.
