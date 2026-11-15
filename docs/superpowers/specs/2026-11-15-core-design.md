# Bleach Work/Private Rice Balance: Core Design

Status: proposed for review  
Date: 2026-11-15  
Scope: package 1 of 3, the core installer and runtime  
Target repository: `diononline-bleach-work-rice-balance`

## 1. Purpose

Build a reproducible, configurable KDE Plasma 6 and Noctalia rice for Arch-based
systems. A new user should be able to clone the repository, run one installer,
choose their applications, map their displays, and get a working desktop with
separate Work and Private application sets.

The design must work for the current three-monitor layout and for a future
single ultrawide display. Display connectors, activity identifiers, user paths,
and application package choices must not be hard-coded in the repository.

## 2. Goals

- Install all required rice dependencies and selected applications on Arch or
  CachyOS.
- Detect KDE Plasma 6 and Noctalia before changing the system.
- Detect connected outputs and provide a placement preset for triple-monitor and
  ultrawide layouts.
- Central configuration file with outputs, zones, applications, placement,
  startup sets, autostart sets, shell widgets, and theme settings.
- Generate KWin placement scripts, Noctalia configuration, systemd units, and
  runtime configuration from the central configuration.
- Provide a local web configurator for editing placement visually.
- Keep the repository free of personal links, personal hostnames, VPS details,
  credentials, and user-specific identifiers.
- Publish documentation in English.
- Do not redistribute copyrighted wallpaper files.

## 3. Non-Goals

- Installing a complete operating system, drivers, bootloader, or desktop
  environment.
- Theming the Plasma login screen, Plymouth, or the boot splash. These are
  optional follow-up work because they require system-level authentication.
- Distributing or automatically scraping copyrighted wallpaper images.
- Bundling personal services such as DSH, private VPS endpoints, or Tailscale
  hostnames.
- Patching KWin itself.
- Supporting non-Arch distributions in the core installer.

## 4. Required Prerequisites

The installer requires:

- Arch Linux or CachyOS with `pacman`.
- An existing KDE Plasma 6 session with KWin.
- Noctalia 5.5.0 or newer.
- An AUR helper (`paru` or `yay`). The installer stops with instructions if no
  helper is available; it does not bootstrap an AUR helper itself.
- An active graphical user session.

Required official packages are installed by the installer. Optional AUR
packages are installed only after the user selects the corresponding
application and the installer confirms the AUR helper is available.

## 5. Repository Layout

```text
.
├── README.md
├── LICENSE
├── install.sh
├── uninstall.sh
├── bin/
│   ├── rice
│   ├── rice-config
│   ├── rice-startup
│   └── rice-theme
├── defaults/
│   ├── rice.toml
│   ├── apps.toml
│   └── layouts/
│       ├── triple.toml
│       ├── single-split.toml
│       └── ultrawide.toml
├── docs/
│   ├── INSTALL.md
│   ├── CONFIGURATION.md
│   ├── ARCHITECTURE.md
│   ├── PLACEMENT.md
│   ├── STARTUP.md
│   ├── THEMING.md
│   ├── ASSETS.md
│   ├── TROUBLESHOOTING.md
│   └── superpowers/specs/
├── plugins/
│   ├── media/
│   ├── themes/
│   ├── cheatsheet/
│   └── profile/
├── src/rice/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── installer.py
│   ├── outputs.py
│   ├── activities.py
│   ├── apps.py
│   ├── apply.py
│   ├── generate.py
│   ├── daemon.py
│   └── web.py
├── src/web/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── templates/
│   ├── kwin/main.js.in
│   ├── noctalia/rice.toml.in
│   ├── systemd/*.service.in
│   └── desktop/*.desktop.in
├── assets/
│   └── wallpapers/
│       └── manifest.toml
├── showcase/
│   └── ATTRIBUTION.md
└── tests/
```

## 6. Configuration Model

The canonical configuration is TOML at:

```text
$XDG_CONFIG_HOME/rice/rice.toml
```

`tomllib` reads it. `python-tomli-w` writes it. The installer installs
`python-tomli-w` as a required package. The configurator never writes partial
TOML; it validates a complete document and replaces the file atomically.

### 6.1 Metadata

```toml
[meta]
schema_version = 1
profile_name = "default"
```

### 6.2 Outputs

```toml
[[output]]
id = "main"
role = "main"
connector = "DP-1"
primary = true
```

Supported roles are `main`, `side`, `portrait`, and `custom`. The installer
fills `connector` from `kscreen-doctor -j` and lets the user change it. A
single-output setup uses `main` only. The configurator can map any role to any
connected output.

If a configured connector is absent at runtime, placement for that output is
skipped with a warning. Applications still launch.

### 6.3 Zones

Zones are rectangles relative to the usable output area. The usable area
excludes exclusive shell reserves such as the top bar.

```toml
[[zone]]
id = "center-left"
output = "main"
kind = "app"
x = 0.24
y = 0.00
w = 0.25
h = 1.00
gap_px = 8

[[zone]]
id = "edge-left"
output = "main"
kind = "shell"
x = 0.00
y = 0.00
w = 0.22
h = 1.00
```

Rules:

- `kind = "app"` zones accept application placement.
- `kind = "shell"` zones host desktop widgets and are not app placement
  targets.
- `x + w <= 1` and `y + h <= 1`.
- Zero-width or zero-height zones are invalid.
- Overlapping app zones are allowed; later placement rules take precedence.
- `gap_px` is applied inside the zone when a window is placed.

### 6.4 Applications

```toml
[[app]]
id = "opencode"
name = "OpenCode"
command = ["opencode"]
wm_class = "ai.opencode.desktop"
package = "opencode-bin"
optional = true
activities = ["private", "work"]

[[app]]
id = "work-browser"
name = "Work Browser"
command = ["firefox"]
wm_class = "firefox"
package = "firefox"
optional = true
activities = ["work"]
```

App identifiers are stable internal IDs. Commands are argv arrays and are never
passed through a shell. The installer resolves optional package choices and
writes the selected commands into the generated runtime configuration.

The repository ships no personal app entries. DSH, VPS endpoints, Tailscale
hosts, and private URLs are not part of the catalog.

### 6.5 Placement

```toml
[[placement]]
app = "work-browser"
activity = "work"
zone = "center-left"
mode = "normal"

[[placement]]
app = "private-browser"
activity = "private"
zone = "center-left"
mode = "maximized"

[[placement]]
app = "discord"
activity = "private"
zone = "portrait-full"
mode = "fullscreen"
```

Supported modes are `normal`, `maximized`, and `fullscreen`. A placement can
optionally include `match_title` and `priority`. The generated KWin script uses
window class first, then the optional title match. If multiple rules match, the
highest priority wins.

The same zones remain in place across Work and Private. Switching activity
changes which application occupies a zone, not the zone geometry.

### 6.6 Activities

```toml
[activities.private]
name = "Private"
kde_id = ""

[activities.work]
name = "Work"
kde_id = ""
```

The installer looks up KDE activities by name through the Activity Manager
D-Bus service. If a named activity does not exist, the installer offers to
create it. The resolved UUID is written to `kde_id`. No activity UUID is
committed to the repository.

### 6.7 Startup and Autostart

Startup means at login. Autostart means the first time an activity becomes
active in the current login session.

```toml
[startup]
always = ["gpu-recorder-ui"]
private = ["steam", "private-browser", "discord", "youtube-music", "claude", "opencode"]

[autostart.private]
apps = []

[autostart.work]
apps = ["work-browser", "slack", "hero-town", "claude"]
```

Rules:

- `startup.always` is launched once at login after Noctalia and KWin are ready.
- `startup.private` is launched once at login when Private is the initial
  activity.
- `autostart.<activity>` is launched once per session when that activity is
  first entered.
- The initial activity is Private by default and is configurable.
- Work applications are not started at login unless explicitly listed in
  `startup.private`.
- A per-session marker in `$XDG_RUNTIME_DIR/rice/` prevents duplicate
  autostart runs.
- The configurator exposes separate Startup and Autostart tabs.

### 6.8 Shell Widgets

```toml
[[desktop_widget]]
id = "clock"
plugin = "clock"
zone = "edge-right-top"
output = "main"
scale = 1.0

[[desktop_widget]]
id = "media"
plugin = "rice/media:desktop"
zone = "edge-left-middle"
output = "main"
scale = 1.0
```

The generator converts zones into Noctalia desktop-widget coordinates (`cx`,
`cy`) and writes them into the generated Noctalia include. The top bar remains
a top, full-width element. Shell widget zones are excluded from app placement.

### 6.9 Theme and Wallpapers

```toml
[theme]
wallpaper_dir = "$HOME/Pictures/rice-wallpapers"
random_on_login = true
hourly_rotation = true
transition = "fade"
transition_duration_ms = 1200
pause_on_fullscreen = true
pause_when_idle = true
same_image_all_outputs = true
```

The theme engine applies the same image to every output by default, using a
portrait crop on portrait outputs. A future release can add per-output theme
sets.

Wallpaper files are not stored in the repository. `assets/wallpapers/manifest.toml`
contains only metadata:

```toml
[[wallpaper]]
id = "example"
file = "example.png"
source = "https://example.invalid/source"
artist = "Example Artist"
license = "private-personal-use-only"
sha256 = ""
```

The installer checks the configured wallpaper directory. Missing files produce
a list of source links and artist credits. Core does not scrape or download
copyrighted images. Users download them for private use or provide their own
licensed images.

## 7. Configurator

### 7.1 Command

`rice-config` starts a local HTTP server on `127.0.0.1` with a random port,
writes a one-time bearer token, and opens the UI in the default browser. It
binds localhost only and exits when the last session ends.

### 7.2 UI Structure

Tabs:

- **Apps**: choose work browser, private browser, Claude variant, YouTube Music,
  Steam, Discord, OpenCode, terminal, and custom apps.
- **Outputs**: map roles to detected connectors and show resolution.
- **Layout**: canvas per output with draggable and resizable app and shell
  zones, snapping, gap control, and a triple/ultrawide/custom preset selector.
- **Placement**: table of app, activity, zone, mode, and priority.
- **Startup**: login sets.
- **Autostart**: Private and Work sets.
- **Widgets**: desktop widget zones and scale.
- **Theme**: wallpaper directory, rotation, transitions.
- **Apply**: validation summary and apply button.

The UI is English. Documentation is English.

### 7.3 Backend API

```text
GET  /api/health
GET  /api/state
GET  /api/outputs
PUT  /api/config
POST /api/validate
POST /api/apply
POST /api/backup
POST /api/restore
```

All mutating requests require the session bearer token. The backend validates
the complete config, writes a timestamped backup, writes TOML atomically, and
then invokes the same `rice apply` path as the CLI.

The backend never executes arbitrary configured commands during validation.
Custom commands are only started by the runtime after explicit user action.

## 8. Runtime Components

### 8.1 `rice` CLI

```text
rice install [--dry-run] [--yes] [--no-packages]
rice apply
rice doctor
rice startup
rice activity <private|work>
rice assets status
rice theme next|prev|random
rice uninstall
```

The CLI is Python and uses only the standard library plus `python-tomli-w` for
TOML writing.

### 8.2 `rice-daemon`

A user D-Bus service, started through systemd, exposes the operations that KWin
shortcuts need:

- switch activity
- run startup
- toggle theme panel
- open Acer/portrait player
- media controls
- fullscreen state for theme rotation guards

The daemon reads the generated runtime configuration and writes logs to
`$XDG_STATE_HOME/rice/logs/`.

### 8.3 Generated Artifacts

`rice apply` produces all runtime artifacts:

- `$XDG_DATA_HOME/kwin/scripts/rice-placement/contents/code/main.js`
- `$XDG_DATA_HOME/kwin/scripts/rice-placement/metadata.json`
- `$XDG_CONFIG_HOME/noctalia/rice.toml`
- `$XDG_CONFIG_HOME/systemd/user/rice-*.service`
- `$XDG_STATE_HOME/rice/runtime.json`
- launcher and startup entries in the configured application menu

`rice apply` then:

1. runs `systemctl --user daemon-reload`
2. reloads the KWin script
3. runs `noctalia msg config-reload`
4. restarts `rice-daemon`
5. prints a summary and any skipped rules

The generated Noctalia file uses only `rice_*` identifiers so it does not
overwrite a user's unrelated Noctalia widgets. The installer adds it as a
normal Noctalia config file; Noctalia reads all `*.toml` files in its config
directory.

## 9. Installer Flow

`install.sh` is a small bootstrap that checks for Python 3.11 or newer and
executes `src/rice/installer.py`. The installer:

1. Verifies Arch/CachyOS, `pacman`, KDE Plasma 6, KWin, Noctalia, and an AUR
   helper.
2. Prints what will be changed and accepts `--dry-run`.
3. Asks for application choices:
   - work browser: Chrome or Firefox
   - private browser: Brave or Chromium
   - Claude: Desktop or Code
   - YouTube Music: on/off
   - Steam: on/off
   - Discord: on/off
   - OpenCode: on/off
   - terminal: Alacritty or Kitty
4. Installs required packages and selected optional packages.
5. Detects outputs and activities, then selects a layout preset.
6. Writes `rice.toml`, backups, generated artifacts, plugins, KWin script, and
   systemd units.
7. Enables the units and KWin script.
8. Runs `rice apply` and a health check.
9. Prints the next steps and any unavailable optional apps.

Every overwritten file is backed up under
`$XDG_STATE_HOME/rice/backups/<timestamp>/`. The uninstall command restores the
latest backup and disables only units and scripts owned by the installer.

The installer never changes system-wide files unless a future optional login
theme step is explicitly selected. Core does not require root beyond `pacman`.

## 10. Default Layout Presets

### 10.1 Triple Monitor

- `main`: full app area, central 50/50 split for primary apps.
- `side`: left and right app halves.
- `portrait`: full-height app area.
- Shell widgets: outer edges of `main` and unused space on `side`.
- Default placement mirrors the current setup: Brave/Steam on main, YouTube and
  Claude on side-left, OpenCode on side-right, Discord on portrait-full.

### 10.2 Ultrawide

One `main` output with four columns:

```text
edge-left | center-left | center-right | edge-right
```

The center two zones are the main work/private tiles. The outer zones host
clock, calendar, media, lyrics, and status widgets so they remain visible while
the center is occupied. The top bar remains full-width.

### 10.3 Single Split

One output with optional edge rails and two center tiles. Used for a normal
16:9 display or a narrow custom canvas.

## 11. Startup Behavior

At login, `rice-startup.service` runs `rice startup` after the graphical
session and Noctalia are ready. It:

1. sets the configured initial activity
2. launches `startup.always`
3. launches `startup.private` when Private is initial
4. marks startup complete

The KWin shortcut dispatcher calls `rice activity <role>`, which switches the
KDE activity and launches the matching autostart set once per session.

Work applications are never launched by the default login set. The installer
and configurator show the distinction explicitly.

## 12. Validation and Error Handling

The config validator checks:

- schema version
- required IDs and unique IDs
- output role references
- zone bounds and positive size
- app and placement references
- activity references
- command is a non-empty argv array
- startup/autostart app references
- wallpaper directory exists or is empty
- no parent-directory traversal in configured paths

Apply is transactional:

- config validated before any file is written
- backups before overwrite
- generated files written to temporary files and renamed
- KWin reload and Noctalia reload reported independently
- a failed optional app launch does not abort the rest of startup

If KDE, KWin, Noctalia, or the AUR helper is missing, the installer stops with a
specific error and does not partially install.

## 13. Security and Privacy

- No personal hostnames, IP addresses, VPS names, Tailscale addresses, tokens,
  API keys, or user-specific URLs are committed.
- No wallpaper binaries are committed.
- Paths use XDG environment variables and `$HOME`; no literal `/home/<user>`.
- The configurator binds `127.0.0.1` only and uses a per-session bearer token.
- App commands are argv arrays. No generated command uses shell interpolation.
- Custom apps are marked as user-supplied and require confirmation before first
  launch.
- The repository contains a PII scan test that fails on private IPv4 ranges other than loopback,
  Tailscale hostnames, SSH/VPS references, and hard-coded home directories.

## 14. Testing

Automated:

- config parser and schema validation tests
- zone geometry tests for triple, single, and ultrawide presets
- output mapping tests with synthetic `kscreen-doctor -j` fixtures
- generated KWin JavaScript syntax check with `node --check`
- generated Noctalia TOML parse tests
- startup/autostart resolver tests with a fake runtime directory
- installer `--dry-run` snapshot tests
- PII and hard-coded path scan
- shell syntax checks for `install.sh` and wrappers

Manual:

- install on a clean Arch/CachyOS VM with KDE and Noctalia
- triple-monitor placement matrix
- single ultrawide with two center tiles
- missing monitor fallback
- Work/Private switching without duplicate autostarts
- configurator edit, validate, apply, backup, restore
- uninstall and restore

## 15. Documentation

All documentation is English:

- `README.md`: what the rice is, screenshots using only own or CC0 demo assets,
  install command, supported systems, asset policy.
- `docs/INSTALL.md`: prerequisites, package choices, dry-run, recovery.
- `docs/CONFIGURATION.md`: complete config reference.
- `docs/ARCHITECTURE.md`: generated artifacts and data flow.
- `docs/PLACEMENT.md`: outputs, zones, presets, ultrawide model.
- `docs/STARTUP.md`: startup vs autostart, activity semantics.
- `docs/THEMING.md`: theme rotation, transitions, wallpaper directory.
- `docs/ASSETS.md`: no bundled copyrighted images, manifest format, artist
  credits, personal-use limits.
- `docs/TROUBLESHOOTING.md`: common KDE, Noctalia, AUR, and display issues.

## 16. Licensing

- Source code: MIT.
- Documentation: MIT unless a file states otherwise.
- Only own, public-domain, or CC0 images may be committed under `showcase/`.
- Wallpaper manifest links and artist names are attribution, not a license to
  redistribute.
- The repository does not include third-party wallpaper files.

## 17. Delivery Phases

### Phase 1: Core

Repository scaffold, config schema, output and activity detection, installer,
apply pipeline, KWin and Noctalia generators, startup and autostart resolver,
asset manifest, backup and uninstall, English docs, tests.

### Phase 2: Configurator

Local web UI, canvas zone editor, app and activity assignment, startup and
autostart tabs, validation, apply/backup/restore.

### Phase 3: Presentation and Optional System Integration

CC0 showcase assets, screenshots, optional Plasma login and boot-splash
integration behind explicit administrator approval, packaging polish.

## 18. Acceptance Criteria

- A supported Arch/CachyOS user with KDE Plasma 6 and Noctalia 5.5+ can run the
  installer, choose apps, and get a working desktop.
- The triple-monitor preset places Brave/Steam, YouTube/Claude, OpenCode, and
  Discord in the documented zones.
- A single ultrawide uses two center tiles and keeps shell widgets at the outer
  edges.
- Work applications start only when Work is entered, not at login.
- Startup sets are not duplicated across logins.
- The configurator can add, remove, move, and resize zones and apply the result.
- No personal links, PII, or wallpaper binaries exist in the repository.
- All docs are English and all generated files are reproducible from
  `rice.toml`.
