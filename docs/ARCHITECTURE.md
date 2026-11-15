# Architecture

The core backend turns one TOML document into a set of generated desktop
artifacts. There is no persistent server and no database. Every run starts from
the configuration file, detects the live session where needed, and writes plain
files into XDG directories.

## Module Map

| Module | Responsibility |
| --- | --- |
| `rice.config` | Load TOML, validate references and geometry, write TOML atomically. |
| `rice.paths` | Resolve XDG base directories and the configuration path. |
| `rice.outputs` | Parse `kscreen-doctor -j` into output records. |
| `rice.activities` | List, create, and switch KDE activities through `qdbus6`. |
| `rice.apps` | Read the application catalog and resolve installer choices into stable app ids. |
| `rice.layouts` | Pick a preset, build preset zones, and derive default placements. |
| `rice.generate` | Render KWin rules, Noctalia include, runtime JSON, and systemd units. |
| `rice.apply` | Validate, back up, write, and reload generated artifacts. |
| `rice.startup` | Launch login startup sets and per-activity autostart sets. |
| `rice.theme` | Discover wallpapers, rotate them, and guard rotation. |
| `rice.daemon` | Expose session actions over the user D-Bus. |
| `rice.installer` | Preflight, package planning, runtime copy, initial config, uninstall. |
| `rice.cli` | The `rice` command surface. |

## Data Flow

```text
defaults/rice.toml          defaults/apps.toml
        │                          │
        │  installer choices       │
        ▼                          ▼
rice.config.validate  ◄──  rice.apps.resolve_choices
        │
        ▼
$XDG_CONFIG_HOME/rice/rice.toml
        │
        ├── rice.generate.generate_kwin      → main.js
        ├── rice.generate.generate_noctalia  → noctalia/rice.toml
        ├── rice.generate.generate_systemd   → systemd/user/rice-*.service
        └── rice.generate.generate_runtime   → state/rice/runtime.json
        │
        ▼
rice.apply: backup → atomic write → reload commands
        │
        ▼
KWin script, Noctalia include, user units, runtime JSON
```

The installer is the only component that composes a new configuration from
hardware detection and user choices. The CLI and future configurator operate on
an existing configuration.

## Generated Artifacts

`rice apply` produces these paths:

| Path | Producer | Purpose |
| --- | --- | --- |
| `$XDG_DATA_HOME/kwin/scripts/rice-placement/contents/code/main.js` | `generate_kwin` | KWin JavaScript that places matching windows in zones. |
| `$XDG_DATA_HOME/kwin/scripts/rice-placement/metadata.json` | `apply` | KWin script manifest declaring the JavaScript entry point. |
| `$XDG_CONFIG_HOME/noctalia/rice.toml` | `generate_noctalia` | Noctalia desktop-widget anchors with `rice_` identifiers. |
| `$XDG_CONFIG_HOME/systemd/user/rice-daemon.service` | `generate_systemd` | User D-Bus daemon. |
| `$XDG_CONFIG_HOME/systemd/user/rice-startup.service` | `generate_systemd` | One-shot login startup runner. |
| `$XDG_CONFIG_HOME/systemd/user/rice-theme-boot.service` | `generate_systemd` | One-shot boot wallpaper selection. |
| `$XDG_CONFIG_HOME/systemd/user/rice-theme-hourly.service` | `generate_systemd` | One-shot hourly rotation job. |
| `$XDG_CONFIG_HOME/systemd/user/rice-theme-hourly.timer` | `generate_systemd` | Hourly timer for the rotation job. |
| `$XDG_STATE_HOME/rice/runtime.json` | `generate_runtime` | Runtime state consumed by startup, autostart, daemon, and theme. |

Templates live under `templates/`. Units reference the installed wrapper as
`%h/.local/bin/rice`, so generated files contain no absolute user path.

## Apply Pipeline

`apply_config` performs these steps in order:

1. Load the configuration with `tomllib`.
2. Validate sections, ids, references, zone bounds, commands, and startup sets.
3. Build the complete artifact map in memory.
4. On dry-run, return the map as the changed-path list and stop. No directory is
   created and no command runs.
5. Back up existing versions of every planned file under
   `$XDG_STATE_HOME/rice/backups/<timestamp>/`.
6. Write each artifact to a temporary file in its destination directory, flush,
   and rename it into place atomically.
7. Run the reload commands.

Reload order:

```text
systemctl --user daemon-reload
systemctl --user enable --now rice-daemon.service rice-startup.service
kwriteconfig6 --file kwinrc --group Plugins --key rice-placementEnabled true
qdbus6 org.kde.KWin /KWin reconfigure
noctalia msg config-reload
```

Apply enables the daemon and startup units. The boot and hourly theme units are
generated but not enabled; enable them manually when automatic rotation is
wanted:

```bash
systemctl --user enable --now rice-theme-boot.service rice-theme-hourly.timer
```

Reload failures are not fatal to the file write. Each command is attempted and
the run continues.

## Runtime JSON

`$XDG_STATE_HOME/rice/runtime.json` is the small state document shared by the
runtime commands. It contains:

| Key | Content |
| --- | --- |
| `startup` | The `startup.always` and `startup.private` lists. |
| `autostart` | Per-activity app lists. |
| `apps` | Full app entries keyed by id, including argv commands. |
| `zones` | Zone records keyed by id. |
| `activities` | Activity roles with names and resolved KDE ids. |
| `theme` | Wallpaper directory, outputs, and rotation flags. |

The daemon loads this file once at start. Rerun `rice apply` and restart the
daemon after changing the configuration.

## KWin Script Model

The generated `main.js` contains a static `RULES` array. Each rule has a window
class, optional title substring, activity id, target connector, relative zone
rectangle, gap, and mode. At runtime the script:

- watches window creation and activation,
- matches the lowercased window class first and the title substring second,
- checks that the rule activity is current,
- resolves the output by connector name and the usable client area,
- converts relative zone coordinates to pixels with the configured gap,
- places the window and optionally maximizes or fullscreens it,
- remembers placement per window and activity so a window is not moved again
  when it is already in the right activity.

The script also reports fullscreen state to the rice D-Bus service so the theme
engine can pause rotation. Placement is best effort: an absent connector or a
window that KWin will not move is skipped without aborting the script.

## D-Bus Daemon

| Item | Value |
| --- | --- |
| Bus name | `org.rice.Rice` |
| Object path | `/Rice` |
| Service unit | `rice-daemon.service` (D-Bus activated, user session) |

Methods:

| Method | Signature | Action |
| --- | --- | --- |
| `SwitchActivity` | `s` | Switch to the activity role and run its autostart set once. |
| `RunStartup` | none | Run the login startup sets. |
| `SetFullscreen` | `sb` | Record fullscreen state for one output. |
| `FullscreenActive` | returns `b` | Whether any output currently reports fullscreen. |
| `ThemeNext` | none | Apply the next wallpaper. |
| `ThemePrevious` | none | Apply the previous wallpaper. |

The daemon keeps fullscreen state in memory. It does not persist anything and
does not write logs of its own; inspect it with the user journal.

## State And Markers

| Path | Lifetime | Purpose |
| --- | --- | --- |
| `$XDG_STATE_HOME/rice/runtime.json` | persistent | Generated runtime document. |
| `$XDG_STATE_HOME/rice/theme-current` | persistent | Last wallpaper path, used to avoid repeats. |
| `$XDG_STATE_HOME/rice/backups/<timestamp>/` | persistent | Pre-overwrite file copies. |
| `$XDG_RUNTIME_DIR/rice/*.done` | login session | Startup and autostart deduplication markers. |

Runtime markers disappear when the session ends, which is why autostart runs
once per login rather than once per machine boot.

## Failure Model

- Invalid configuration fails before any write.
- A missing wallpaper directory is only an error for a theme command, not for
  apply.
- A missing output connector skips placement for that output.
- A missing app command in runtime JSON fails the specific startup call.
- A failing package command stops the install at that command; fix the package
  cause and rerun.
- Uninstall removes only rice-owned paths and keeps backups.

## Future Work

The shell plugin port, custom bar, keybinding pack, and local web configurator
are separate plans. They are expected to consume the same configuration and
apply pipeline rather than introducing a second source of truth. The core
pipeline is deliberately file based so those components can reuse it.
