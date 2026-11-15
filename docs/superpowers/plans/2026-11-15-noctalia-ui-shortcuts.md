# Noctalia Shell and Shortcut Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Noctalia bar, custom panels/plugins, CLI widgets, and KWin shortcuts to the core rice while keeping every path, output, and activity configurable.

**Architecture:** The core installer already installs `src/rice`, templates, defaults, assets, and any `plugins/` directory. This plan adds a static Noctalia base config, generated desktop-widget and bar sections, four MIT-licensed Noctalia plugins, CLI commands for panel/quickstart/arrange actions, and a generated shortcut block in the KWin script. Noctalia has no include mechanism, so the generated `config.toml` must merge the base and generated sections and back up the previous file.

**Tech Stack:** Python 3.11+, `tomli-w`, Noctalia 5.5+ TOML/Luau plugin API 51, KDE Plasma 6/KWin scripting, systemd user units, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-core-design.md`

## Global Constraints

- Arch Linux or CachyOS only; KDE Plasma 6, KWin, Noctalia 5.5+.
- Runtime Python dependencies: standard library, `python-tomli-w`, `python-dbus`, `python-gobject`.
- All user paths use `$HOME` and XDG variables. No literal `/home/<user>` in committed files.
- No personal links, personal hostnames, VPS/Tailscale endpoints, credentials, or IPs.
- No wallpaper binaries. Asset metadata only.
- English documentation and user-facing labels/tooltips.
- No system-wide writes except package installation through pacman/AUR.
- Work apps do not start at login; activity startup remains separate from autostart.
- Output placement uses roles and relative zones, never hard-coded connector names.
- `rice.toml` remains canonical; generated Noctalia/KWin/systemd files derive from it.
- Every task ends with a passing test run and a commit.
- No web configurator work in this plan.

---

## File Structure

```text
defaults/noctalia/config.toml
plugins/themes/plugin.toml
plugins/themes/panel.luau
plugins/cheatsheet/plugin.toml
plugins/cheatsheet/panel.luau
plugins/profile/plugin.toml
plugins/profile/widget.luau
plugins/media/plugin.toml
plugins/media/service.luau
plugins/media/desktop.luau
plugins/media/player_panel.luau
plugins/media/queue_panel.luau
src/rice/cli.py
src/rice/theme.py
src/rice/generate.py
src/rice/apply.py
src/rice/startup.py
src/rice/installer.py
templates/kwin/main.js.in
tests/test_generate.py
tests/test_apply.py
tests/test_cli.py
tests/test_theme.py
tests/test_noctalia_assets.py
tests/test_pii.py
docs/NOCTALIA.md
docs/SHORTCUTS.md
README.md
```

### Task 1: Noctalia Base Config and Apply Integration

**Files:**
- Create: `defaults/noctalia/config.toml`
- Modify: `src/rice/generate.py`
- Modify: `src/rice/apply.py`
- Modify: `src/rice/installer.py`
- Test: `tests/test_generate.py`
- Test: `tests/test_apply.py`
- Test: `tests/test_noctalia_assets.py`

**Interfaces:**
- Consumes: `generate_noctalia(config) -> str`, `apply_config(...)`, `config_home()`.
- Produces: `load_noctalia_base() -> dict`; `generate_noctalia(config) -> str` returns a complete `config.toml`; `apply_config` writes `$XDG_CONFIG_HOME/noctalia/config.toml`; `build_initial_config` keeps the theme section.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_generate.py
import tomllib

from rice.generate import generate_noctalia


def test_noctalia_merges_base_bar_and_widgets():
    text = generate_noctalia(CONFIG)
    data = tomllib.loads(text)
    assert data["bar"]["main"]["position"] == "top"
    assert data["desktop_widgets"]["enabled"] is True
```

```python
# tests/test_noctalia_assets.py
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "defaults/noctalia/config.toml"


def test_noctalia_base_is_valid_toml():
    with CONFIG.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["bar"]["order"] == ["main"]


def test_noctalia_base_has_no_personal_or_connector_paths():
    text = CONFIG.read_text(encoding="utf-8")
    assert "/home/" not in text
    assert "HDMI-A-1" not in text
    assert "DP-1" not in text
    assert "DP-2" not in text
    assert "rice-theme " not in text
    assert "rice-activity " not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_generate.py::test_noctalia_merges_base_bar_and_widgets tests/test_noctalia_assets.py -v`  
Expected: FAIL because the base file and merge logic do not exist.

- [ ] **Step 3: Create the sanitized Noctalia base config and merge logic**

Create `defaults/noctalia/config.toml` from the sanitized live Noctalia config. It must contain the shell, panel, theme, wallpaper, bar, widget, and desktop-widgets sections, but:

- remove every `[bar.main.monitor.*]` block and every connector name;
- translate German labels/tooltips to English (`Work`, `Private`, `Start`, `Layout`);
- replace old command actions with `exec rice ...`:

```toml
# Required action replacements
[widget.cheatsheet]
type = "custom_button"
glyph = "keyboard"
tooltip = "Shortcuts"

[widget.cheatsheet.actions]
left = "exec rice cheatsheet"

[widget.themes]
type = "custom_button"
glyph = "palette"
tooltip = "Wallpapers and palette"

[widget.themes.actions]
left = "exec rice theme panel"

[widget.work]
type = "custom_button"
glyph = "briefcase"
label = "Work"
tooltip = "Switch to Work"

[widget.work.actions]
left = "exec rice activity work"

[widget.private]
type = "custom_button"
glyph = "home"
label = "Private"
tooltip = "Switch to Private"

[widget.private.actions]
left = "exec rice activity private"

[widget.quickstart]
type = "custom_button"
glyph = "rocket"
label = "Start"
tooltip = "Start missing apps in the current activity"

[widget.quickstart.actions]
left = "exec rice quickstart"

[widget.layout]
type = "custom_button"
glyph = "layout-grid"
label = "Layout"
tooltip = "Reapply the default window layout"

[widget.layout.actions]
left = "exec rice arrange"
```

Use `bar.order = ["main"]` and keep the existing `bar.main` start/end widget lists. Remove all `[desktop_widgets.widget.*]` entries from the base; the generator supplies them.

Modify `src/rice/generate.py`:

```python
NOCTALIA_BASE = Path(__file__).resolve().parents[2] / "defaults/noctalia/config.toml"


def load_noctalia_base() -> dict:
    with NOCTALIA_BASE.open("rb") as handle:
        return tomllib.load(handle)


def generate_noctalia(config: dict) -> str:
    data = load_noctalia_base()
    widgets = [_widget_anchor(config, widget) for widget in config.get("desktop_widget", [])]
    data["desktop_widgets"] = {
        "enabled": True,
        "schema_version": 2,
        "widget_order": [f"rice_{index}" for index in range(len(widgets))],
        "widget": {f"rice_{index}": widget for index, widget in enumerate(widgets)},
    }
    return tomli_w.dumps(data)
```

Add `import tomllib` at the top of `generate.py`.

Modify `src/rice/apply.py` so the generated path is:

```python
noctalia_dir = config_home() / "noctalia"
generated = {
    ...
    noctalia_dir / "config.toml": generate_noctalia(config),
    ...
}
```

Do not keep the old `rice.toml` include path. Update `installer.py`/`uninstall` only if they reference the old file.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_generate.py tests/test_apply.py tests/test_noctalia_assets.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add defaults/noctalia src/rice/generate.py src/rice/apply.py src/rice/installer.py tests/test_generate.py tests/test_apply.py tests/test_noctalia_assets.py
git commit -m "feat: install merged noctalia config"
git push -u origin feat/noctalia-ui
```

### Task 2: Theme Command Parity and Theme Selector Plugin

**Files:**
- Modify: `src/rice/theme.py`
- Modify: `src/rice/cli.py`
- Create: `plugins/themes/plugin.toml`
- Create: `plugins/themes/panel.luau`
- Test: `tests/test_theme.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `list_wallpapers`, `_apply`, `runtime`, `noctalia`.
- Produces: `rice theme set <path>`, `rice theme refresh`, `rice theme panel`, `rice theme status`; plugin `rice/themes:panel`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_theme.py
from rice.theme import wallpaper_status


def test_wallpaper_status_uses_cache_index(tmp_path):
    (tmp_path / "one.png").write_bytes(b"x")
    status = wallpaper_status(tmp_path)
    assert status["count"] == 1
```

```python
# tests/test_cli.py
def test_cli_help_lists_theme_panel_and_set():
    result = run_cli("theme", "--help")
    assert result.returncode == 0
    for value in ("set", "refresh", "panel", "status"):
        assert value in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_theme.py::test_wallpaper_status_uses_cache_index tests/test_cli.py::test_cli_help_lists_theme_panel_and_set -v`  
Expected: FAIL because CLI choices lack the new subcommands.

- [ ] **Step 3: Implement CLI/theme parity**

Add CLI choices `set`, `refresh`, `panel`, `status` and accept a value for `set`. Implement:

- `set`: resolve path under `theme.wallpaper_dir`, call `_apply`.
- `refresh`: write `$XDG_CACHE_HOME/rice-theme/index.tsv` with `source\tthumbnail\tname`; use `magick` if available; fail clearly if missing.
- `panel`: toggle `rice/themes:panel` via `noctalia msg panel-open`/`panel-close`, matching the old behavior.
- `status`: print the current theme path.

Create the theme selector plugin from the existing local panel, changing:

```lua
local HOME = noctalia.getenv("HOME") or error("HOME is required")
local CACHE = (noctalia.getenv("XDG_CACHE_HOME") or (HOME .. "/.cache")) .. "/rice-theme"
local RICE = HOME .. "/.local/bin/rice"
```

Replace all shell calls with `noctalia.runAsync({ RICE, "theme", ... })` where the API accepts argv; if it only accepts strings, build `RICE .. " theme set " .. shellQuote(source)`. Remove every literal local home path.

- [ ] **Step 4: Run tests and syntax checks**

Run: `.venv/bin/python -m pytest tests/test_theme.py tests/test_cli.py -v`  
Run `luau --version` if available; otherwise document that Luau syntax is checked by Noctalia on plugin load.

- [ ] **Step 5: Commit and push**

```bash
git add src/rice/theme.py src/rice/cli.py plugins/themes tests/test_theme.py tests/test_cli.py
git commit -m "feat: add theme panel and cli parity"
git push
```

### Task 3: Profile and Cheatsheet Plugins

**Files:**
- Create: `plugins/profile/plugin.toml`
- Create: `plugins/profile/widget.luau`
- Create: `plugins/cheatsheet/plugin.toml`
- Create: `plugins/cheatsheet/panel.luau`
- Modify: `src/rice/cli.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_noctalia_assets.py`

**Interfaces:**
- Consumes: `rice activity work|private`, `rice cheatsheet`.
- Produces: bar widget `rice/profile:bar`; panel `rice/cheatsheet:panel`; `rice cheatsheet` command.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli.py
def test_cli_help_lists_cheatsheet_and_quickstart():
    result = run_cli("--help")
    assert "cheatsheet" in result.stdout
    assert "quickstart" in result.stdout
    assert "arrange" in result.stdout
```

```python
# tests/test_noctalia_assets.py
def test_profile_plugin_has_no_hardcoded_activity_uuid():
    text = (ROOT / "plugins/profile/widget.luau").read_text(encoding="utf-8")
    assert "012e885b" not in text
    assert "db345c88" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_cli_help_lists_cheatsheet_and_quickstart tests/test_noctalia_assets.py::test_profile_plugin_has_no_hardcoded_activity_uuid -v`  
Expected: FAIL.

- [ ] **Step 3: Port plugins and commands**

Profile plugin behavior:

- Read `$XDG_STATE_HOME/rice/runtime.json` with `noctalia.readFile` and `noctalia.json.decode`.
- Extract `activities.private.kde_id` and `activities.work.kde_id`.
- Query current activity with `qdbus6` as the old plugin did.
- Render English buttons `Work`/`Private`.
- On click, run `rice activity work` or `rice activity private`; no hard-coded UUID.

Cheatsheet plugin: copy the existing panel, keep its content, change only paths/commands if any. Add `rice cheatsheet` as:

```python
def run_cheatsheet(args):
    subprocess.run(["noctalia", "msg", "panel-toggle", "rice/cheatsheet:panel"], check=True)
    return 0
```

Add `cheatsheet`, `quickstart`, `arrange` parsers. Implement `quickstart` by reading runtime, querying current activity, and launching the matching startup set; implement `arrange` by calling a KWin DBus method added in Task 5 or by re-running `apply` without writing config. If the KWin method does not exist yet, make `arrange` exit with a clear message and wire it in Task 5.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_noctalia_assets.py -v` and the full suite.

- [ ] **Step 5: Commit and push**

```bash
git add src/rice/cli.py plugins/profile plugins/cheatsheet tests/test_cli.py tests/test_noctalia_assets.py
git commit -m "feat: port profile and cheatsheet panels"
git push
```

### Task 4: Media Plugin with Configurable API

**Files:**
- Create: `plugins/media/plugin.toml`
- Create: `plugins/media/service.luau`
- Create: `plugins/media/desktop.luau`
- Create: `plugins/media/player_panel.luau`
- Create: `plugins/media/queue_panel.luau`
- Create: `defaults/noctalia/media.json`
- Test: `tests/test_noctalia_assets.py`

**Interfaces:**
- Consumes: `rice/media` plugin API; optional local media API.
- Produces: disabled-by-default media plugin; `defaults/noctalia/media.json` with `api_url = "http://127.0.0.1:26538/api/v1"` and a comment that users must run their own compatible service.

- [ ] **Step 1: Write the failing asset test**

```python
# tests/test_noctalia_assets.py
def test_media_plugin_is_metadata_only_and_has_no_personal_paths():
    text = (ROOT / "plugins/media/service.luau").read_text(encoding="utf-8")
    assert "/home/" not in text
    assert "API = " in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_noctalia_assets.py::test_media_plugin_is_metadata_only_and_has_no_personal_paths -v`  
Expected: FAIL because the plugin does not exist.

- [ ] **Step 3: Port the media plugin**

Copy the existing media plugin files, replace `local API = "http://127.0.0.1:26538/api/v1"` with:

```lua
local config = noctalia.json.decode(noctalia.readFile(
  (noctalia.getenv("XDG_CONFIG_HOME") or ((noctalia.getenv("HOME") or error("HOME is required")) .. "/.config"))
  .. "/noctalia/media.toml"
) or "{}") or {}
local API = config.api_url or "http://127.0.0.1:26538/api/v1"
```

Replace every `/home/dion` fallback with `HOME`/XDG. Keep the plugin disabled in the base bar until the user enables it; do not add it to `desktop_widgets` automatically.

- [ ] **Step 4: Run tests and PII**

Run: `.venv/bin/python -m pytest tests/test_noctalia_assets.py tests/test_pii.py -v`.

- [ ] **Step 5: Commit and push**

```bash
git add plugins/media defaults/noctalia/media.json tests/test_noctalia_assets.py
git commit -m "feat: add optional media plugin"
git push
```

### Task 5: Bar Actions, Quickstart, Arrange, and KWin Shortcuts

**Files:**
- Modify: `templates/kwin/main.js.in`
- Modify: `src/rice/generate.py`
- Modify: `src/rice/cli.py`
- Create: `src/rice/shortcuts.py`
- Test: `tests/test_generate.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `kwin_rules`, config output roles, `org.rice.Rice` D-Bus.
- Produces: generated shortcut block; `rice arrange`; `rice shortcuts disable-conflicts`; no hard-coded connector names.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_generate.py
def test_generated_kwin_has_configurable_shortcuts():
    js = generate_kwin(CONFIG)
    assert "registerShortcut" in js
    assert "org.rice.Rice" in js
    assert "OUTPUT_ROLES" in js
```

```python
# tests/test_cli.py
def test_cli_help_lists_shortcuts():
    result = run_cli("--help")
    assert "shortcuts" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_generate.py::test_generated_kwin_has_configurable_shortcuts tests/test_cli.py::test_cli_help_lists_shortcuts -v`  
Expected: FAIL.

- [ ] **Step 3: Add shortcuts and commands**

Add a generated `const OUTPUT_ROLES = __OUTPUTS__;` next to `RULES`; populate from config outputs as:

```python
outputs = [
    {"role": output["role"], "connector": output["connector"]}
    for output in config["output"]
]
```

Add `registerShortcut` entries for maximize, minimize, close, terminal, half tiles, cycle window, move to role `main`/`side`/`portrait`, theme next/previous, cheatsheet, and work/private activities. Use `callDBus("org.rice.Rice", "/Rice", "org.rice.Rice", ...)`. Resolve move targets by role at runtime from `OUTPUT_ROLES`, never by connector string.

Add daemon methods used by shortcuts that are missing: `QuickstartWork`, `QuickstartPrivate`, `QuickstartCurrent`, `ToggleCheatSheet`, `ReapplyPlacement`, `OpenTerminal`, `OpenAnimatedTerminal`, `ThemeNext`, `ThemePrevious`, `SwitchActivity`. Keep existing methods.

Implement `rice shortcuts disable-conflicts` as a Python module that uses `dbus` to clear the known conflicting KDE actions, with a systemd unit generated by `generate_systemd`; do not use absolute user paths.

Implement `rice arrange` as a DBus call to `ReapplyPlacement`.

- [ ] **Step 4: Run tests and syntax check**

Run: full pytest, `node --check` on generated KWin JS, and `bash -n install.sh uninstall.sh bin/rice`.

- [ ] **Step 5: Commit and push**

```bash
git add templates/kwin/main.js.in src/rice/generate.py src/rice/cli.py src/rice/shortcuts.py src/rice/daemon.py tests/test_generate.py tests/test_cli.py
git commit -m "feat: generate kwin shortcuts and bar actions"
git push
```

### Task 6: Installer, Docs, PII, and PR

**Files:**
- Modify: `src/rice/installer.py`
- Modify: `src/rice/apply.py`
- Create: `docs/NOCTALIA.md`
- Create: `docs/SHORTCUTS.md`
- Modify: `README.md`
- Modify: `PROJECT_STATUS.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_installer.py`
- Modify: `tests/test_pii.py`

**Interfaces:**
- Consumes: all assets/plugins/commands.
- Produces: installer copies plugins and config; uninstall removes generated Noctalia config and restores backup; public docs; PR.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_installer.py
def test_installer_plan_copies_plugins_and_noctalia_config():
    assert hasattr(installer, "install_tree")
    # assert the repo contains plugin manifests and the Noctalia base
    assert (ROOT / "plugins/themes/plugin.toml").is_file()
    assert (ROOT / "defaults/noctalia/config.toml").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_installer.py::test_installer_plan_copies_plugins_and_noctalia_config -v`  
Expected: FAIL until assets exist.

- [ ] **Step 3: Finish integration and docs**

- Ensure `install_tree` copies `plugins/` when present and writes `defaults/noctalia`.
- Ensure `apply_config` backs up existing `~/.config/noctalia/config.toml`; uninstall removes the generated file and restores the latest backup.
- Update PII scan to include `plugins/` and `defaults/noctalia/`.
- Document the Noctalia merge/backup behavior, plugin list, media API requirement, bar actions, shortcuts, and current limitations.
- Update `PROJECT_STATUS.md` progress and `CHANGELOG.md`.

- [ ] **Step 4: Run all checks**

Run full pytest, `compileall`, `bash -n`, `git diff --check`, and PII.

- [ ] **Step 5: Commit and push, open PR**

```bash
git add src/rice/installer.py src/rice/apply.py docs README.md PROJECT_STATUS.md CHANGELOG.md tests
git commit -m "docs: document noctalia shell and shortcuts"
git push
gh pr create --fill
```

---

## Plan Self-Review

- Spec coverage: Noctalia config, custom panels and bar, theme selector, profile indicator, cheatsheet, media plugin, configurable shortcuts, installer/docs/PII.
- Plan 3 (web configurator) is excluded.
- No wallpaper binaries, personal paths, hostnames, or credentials.
- Every task has tests, a commit, and a push step.
- Interfaces use `rice` CLI commands and `org.rice.Rice` consistently.
- No TBD or placeholder implementation steps.
