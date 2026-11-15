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
| `rice.generate` | Render KWin rules and shortcuts, the merged Noctalia config, runtime JSON, and systemd units. |
| `rice.apply` | Validate, back up, write, and reload generated artifacts. |
| `rice.startup` | Launch login startup sets and per-activity autostart sets. |
| `rice.theme` | Discover wallpapers, rotate them, and guard rotation. |
| `rice.daemon` | Expose session actions over the user D-Bus. |
| `rice.shortcuts` | Clear KDE global shortcuts that collide with the rice bindings. |
| `rice.installer` | Preflight, package planning, runtime copy, initial config, uninstall. |
| `rice.web` | Loopback HTTP server and JSON API for the browser configurator. |
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
        ├── rice.generate.generate_kwin      → main.js + shortcut block
        ├── rice.generate.generate_noctalia  → noctalia/config.toml
        ├── rice.generate.generate_systemd   → systemd/user/rice-*.service
        └── rice.generate.generate_runtime   → state/rice/runtime.json
        │
        ▼
rice.apply: backup → atomic write → reload commands
        │
        ▼
KWin script, merged Noctalia config, user units, runtime JSON
```

The installer is the only component that composes a new configuration from
hardware detection and user choices. The CLI and the browser configurator both
operate on an existing configuration.

## Generated Artifacts

`rice apply` produces these paths:

| Path | Producer | Purpose |
| --- | --- | --- |
| `$XDG_DATA_HOME/kwin/scripts/rice-placement/contents/code/main.js` | `generate_kwin` | KWin JavaScript that places matching windows in zones and registers shortcut bindings. |
| `$XDG_DATA_HOME/kwin/scripts/rice-placement/arrange.js` | `generate_arrange` | One-shot layout reapply script loaded by `rice arrange`. |
| `$XDG_DATA_HOME/kwin/scripts/rice-placement/metadata.json` | `apply` | KWin script manifest declaring the JavaScript entry point. |
| `$XDG_CONFIG_HOME/noctalia/config.toml` | `generate_noctalia` | Merged Noctalia base and generated desktop-widget anchors with `rice_` identifiers. |
| `$XDG_CONFIG_HOME/systemd/user/rice-daemon.service` | `generate_systemd` | User D-Bus daemon. |
| `$XDG_CONFIG_HOME/systemd/user/rice-startup.service` | `generate_systemd` | One-shot login startup runner. |
| `$XDG_CONFIG_HOME/systemd/user/rice-shortcuts.service` | `generate_systemd` | One-shot cleanup of colliding KDE shortcuts. |
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
systemctl --user enable --now rice-daemon.service rice-startup.service rice-shortcuts.service
kwriteconfig6 --file kwinrc --group Plugins --key rice-placementEnabled true
qdbus6 org.kde.KWin /KWin reconfigure
noctalia msg config-reload
```

Apply enables the daemon, startup, and shortcut units. The boot and hourly theme
units are generated but not enabled; enable them manually when automatic
rotation is wanted:

```bash
systemctl --user enable --now rice-theme-boot.service rice-theme-hourly.timer
```

Reload failures are not fatal to the file write. Each command is attempted and
the run continues.

## Noctalia Merge

Noctalia has no include mechanism, so `generate_noctalia` merges rather than
points. It loads `defaults/noctalia/config.toml`, adds the generated
`desktop_widgets` table, and returns one complete document. `apply` writes that
document over `$XDG_CONFIG_HOME/noctalia/config.toml`.

The generated file starts with `# Noctalia base configuration installed by
rice.`. The oldest backup that lacks that marker is treated as the user's
pre-rice file and restored by uninstall; a hand-written current file is left
untouched. Existing generated files are backed up flat under
`$XDG_STATE_HOME/rice/backups/<timestamp>/`, so the previous `config.toml` is
easy to find.

Plugins are not generated. `install_tree` copies each directory under
`plugins/` to `$XDG_DATA_HOME/noctalia-plugins/<name>/`, where Noctalia reads
manifests. The bar and the default desktop-widget list reference only plugin ids
that exist in that tree.

## Shortcut Model

The generated KWin script contains a `RULES` array, an `OUTPUT_ROLES` array, and
a block of `registerShortcut` calls. Window management runs in KWin directly;
terminal, theme, activity, cheatsheet, quickstart, and arrange actions call
`org.rice.Rice` on `/Rice`. Move bindings resolve a role (`main`, `side`,
`portrait`) to a connector at runtime, so the template contains no connector
name.

The installer assigns roles by output identity, not by list index: the primary
output is `main`, the first non-primary output is `side`, and the second is
`portrait`. `rice.shortcuts` and `rice-shortcuts.service` clear the matching KDE
defaults at login. See [Shortcuts](SHORTCUTS.md).

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
| `QuickstartWork` | none | Launch the Work autostart set. |
| `QuickstartPrivate` | none | Launch the Private startup set. |
| `QuickstartCurrent` | none | Launch the set for the active activity. |
| `ToggleCheatSheet` | none | Toggle the cheatsheet panel. |
| `ReapplyPlacement` | none | Load the generated arrange script through KWin. |
| `OpenTerminal` | none | Launch the configured terminal. |
| `OpenAnimatedTerminal` | none | Launch the configured terminal with the animation variant. |

The daemon keeps fullscreen state in memory. It does not persist anything and
does not write logs of its own; inspect it with the user journal.

## State And Markers

| Path | Lifetime | Purpose |
| --- | --- | --- |
| `$XDG_STATE_HOME/rice/runtime.json` | persistent | Generated runtime document. |
| `$XDG_STATE_HOME/rice/theme-current` | persistent | Last wallpaper path, used to avoid repeats. |
| `$XDG_STATE_HOME/rice/backups/<timestamp>/` | persistent | Pre-overwrite file copies. |
| `$XDG_STATE_HOME/rice/web-backups/<timestamp>/` | persistent | Configurator copies of `rice.toml`. |
| `$XDG_RUNTIME_DIR/rice/*.done` | login session | Startup and autostart deduplication markers. |

Runtime markers disappear when the session ends, which is why autostart runs
once per login rather than once per machine boot.

## Web Configurator

`rice.web` runs a `ThreadingHTTPServer` on `127.0.0.1` with a random port and a
per-start bearer token from `secrets.token_urlsafe(32)`. `rice config` and the
installed `rice-config` wrapper both call `run_server`; the CLI subcommand only
lazily imports the module so `rice --help` never loads the HTTP stack.

The handler has three layers.

1. `do_GET`, `do_PUT`, and `do_POST` route by path against a fixed table.
2. `_require_auth` compares the `Authorization: Bearer` value with
   `hmac.compare_digest` and returns 401 on mismatch.
3. Endpoint methods reuse `rice.config.load_config`, `validate_config`, and
   `save_config`, plus the injected `apply_func` (default `apply_config`), so
   the configurator cannot diverge from the CLI.

Static files come from `WEB_ROOT`, which resolves to `src/web` in both the
checkout and the installed tree, because the installer copies that directory
next to `src/rice`. `STATIC_FILES` is an explicit allowlist mapping, so no
request path reaches the filesystem unchecked. The three assets have no
external references.

`/api/backup` copies `rice.toml` into
`$XDG_STATE_HOME/rice/web-backups/<timestamp>/`. `/api/restore` resolves the
requested path and requires it to sit inside that root before loading and
validating it. Apply stays a separate call, so a restore never triggers a
runtime reload on its own.

The API never executes a command from the document. Application commands stay
argv arrays, and the only side effects are the file writes and reload commands
that `apply_config` already performs.

## Failure Model

- Invalid configuration fails before any write.
- A missing wallpaper directory is only an error for a theme command, not for
  apply.
- A missing output connector skips placement for that output.
- A missing role connector skips only that move shortcut.
- A missing app command in runtime JSON fails the specific startup call.
- A failing package command stops the install at that command; fix the package
  cause and rerun.
- Uninstall removes only rice-owned paths, keeps backups, restores the oldest
  pre-rice Noctalia config when one exists, and leaves wallpapers untouched.

## Future Work

The three plans are implemented. Live verification remains: the Noctalia Luau
plugins, the KWin bindings, the installer and uninstall restore path on a clean
Arch/CachyOS target, and the configurator canvas in a real browser. The core
pipeline is deliberately file based so each surface reuses the same
configuration and apply code path.
