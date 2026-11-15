# Noctalia Shell

The Noctalia layer of rice turns the generated configuration into a working
shell: a bar with rice actions, four MIT-licensed plugins, a theme selector, a
Work/Private indicator, a shortcut cheatsheet, and an optional media companion.
Everything is generated or installed by rice; no Noctalia file is downloaded
from a third party.

## Configuration Model

Noctalia has no include mechanism. rice therefore ships one base document,
`defaults/noctalia/config.toml`, and `rice apply` merges the generated sections
into it before writing the result.

1. `rice.generate.generate_noctalia` loads the base document.
2. It adds a `desktop_widgets` table derived from `desktop_widget` entries in
   `$XDG_CONFIG_HOME/rice/rice.toml`.
3. It writes the merged document to `$XDG_CONFIG_HOME/noctalia/config.toml`.
4. `rice apply` backs up the previous file, writes atomically, and reloads
   Noctalia with `noctalia msg config-reload`.

The generated file starts with the line
`# Noctalia base configuration installed by rice.`. Uninstall uses that marker
to tell a rice-owned file from a hand-written one.

Do not edit the generated file by hand: the next `rice apply` replaces it. Edit
`defaults/noctalia/config.toml` in a checkout when changing the shared base, or
edit the rice configuration for placement and widget anchors.

## Bar Layout

The default bar sits at the top with three regions.

| Region | Members |
| --- | --- |
| Start | `launcher`, `cheatsheet`, `themes`, `group:quick` |
| Center | empty |
| End | `group:stats`, `group:sys`, `group:bg` |

`group:quick` contains `profile`, `quickstart`, and `layout`. `group:stats`
contains `cpu-top`, `ram-top`, and `gpu-top`. `group:sys` contains `network`,
`bluetooth`, `volume`, `notifications`, and `control-center`. `group:bg`
contains `tray`.

Capsule groups use a translucent surface color with a primary border. Change
`capsule_opacity`, `radius`, or `padding` in the base document if the default
does not match your panel scale.

## Bar Actions

The rice widgets are ordinary Noctalia custom buttons or plugin widgets. They
call the installed `rice` wrapper through argv, never through a shell string.

| Widget | Kind | Left click action | CLI equivalent |
| --- | --- | --- | --- |
| `cheatsheet` | custom button | Open the shortcut reference | `rice cheatsheet` |
| `themes` | custom button | Open the wallpaper and palette picker | `rice theme panel` |
| `profile` | `rice/profile:bar` | Switch between Work and Private | `rice activity work` / `rice activity private` |
| `quickstart` | custom button | Start missing apps in the current activity | `rice quickstart` |
| `layout` | custom button | Reapply the default window layout | `rice arrange` |

Every action tolerates a missing display or a stopped daemon by printing one
short error line. See [Shortcuts](SHORTCUTS.md) for the generated bindings.

## Plugins

Plugins are installed when the repository or the installed runtime tree contains
a `plugins/` directory. Each child directory is copied to
`$XDG_DATA_HOME/noctalia-plugins/<name>/`, which is the location Noctalia reads
plugin manifests from.

| Directory | Plugin id | Entries | Purpose |
| --- | --- | --- | --- |
| `plugins/themes` | `rice/themes` | `panel` (`panel.luau`) | Wallpaper grid, palette selection, and theme refresh. |
| `plugins/profile` | `rice/profile` | `widget` (`widget.luau`) | Work/Private switch with an active-activity color mark. |
| `plugins/cheatsheet` | `rice/cheatsheet` | `panel` (`panel.luau`) | Grouped keyboard shortcut reference. |
| `plugins/media` | `rice/media` | `service`, `desktop_widget`, `player`, `queue` | Optional media transport and queue UI. |

All four manifests declare `plugin_api = 51`, `license = "MIT"`, and author
`rice`. The Luau sources use `HOME` and XDG variables only; they contain no
connector names, activity ids, personal paths, or credentials.

## Theme Selector

`rice/themes:panel` lists wallpapers from `theme.wallpaper_dir`, shows the
current theme, and applies a selected entry through the theme CLI. The panel
calls `rice theme set`, `rice theme next`, `rice theme previous`, and
`rice theme refresh` as argv commands.

The CLI keeps the same behavior outside the panel: `rice theme panel` toggles
the panel, `rice theme status` reports the current wallpaper, and `rice theme
refresh` rebuilds the thumbnail index. Rotation and fullscreen guards are
documented in [Theming](THEMING.md).

## Profile Indicator

`rice/profile:bar` reads activity roles and resolved KDE ids from
`$XDG_STATE_HOME/rice/runtime.json`. It highlights the active role and switches
with `rice activity work` or `rice activity private`, so the plugin never hard
codes an activity uuid.

Run `rice apply` after adding or renaming activities; the daemon and the plugin
both read the generated runtime document.

## Cheatsheet

`rice/cheatsheet:panel` is a read-only reference grouped into window, workspace,
theme, and activity sections. It labels displays by role (`Main`, `Side`,
`Portrait`) instead of connector names, so it stays correct on a different
machine. `rice cheatsheet` toggles the panel through `noctalia msg`.

## Media Plugin

`rice/media` is opt-in. It is not part of the base bar and not part of the
default `desktop_widget` list, so an install without a media backend has no
broken panel.

The plugin needs a local service that exposes a compatible HTTP API. The
service is not bundled. To configure the plugin:

1. Copy the shipped defaults file from the installed tree:

   ```bash
   mkdir -p "$XDG_CONFIG_HOME/noctalia"
   cp "${XDG_DATA_HOME:-$HOME/.local/share}/rice/defaults/noctalia/media.json" \
      "$XDG_CONFIG_HOME/noctalia/media.json"
   ```

2. Set `api_url` to the address of your service. The shipped value is
   `http://127.0.0.1:26538/api/v1`.
3. Add `rice/media` entries to your bar or desktop widgets, then reload
   Noctalia.

The plugin tolerates a missing or malformed `media.json`: it reports the
configuration problem and keeps the rest of the shell running. The default file
is JSON with an explanatory `_comment` key next to `api_url`.

## Desktop Widgets

`desktop_widget` entries in the rice configuration place third-party widgets at
the center of a configured zone. `apply` converts each entry into a
`desktop_widgets.widget` record with an output connector, pixel center, and
scale. `widget_order` keeps the configured order and uses `rice_<n>` keys.

The base document ships an empty `desktop_widgets` table, so an install without
widget entries is still valid TOML and shows no phantom widgets.

## Install And Uninstall

The installer copies `defaults/`, `templates/`, `assets/`, `src/rice/`, and any
`plugins/` directory. It does not write a second copy of the Noctalia base into
the configuration directory; `apply` performs that merge.

Uninstall removes the generated `$XDG_CONFIG_HOME/noctalia/config.toml` and the
rice plugin directories under `$XDG_DATA_HOME/noctalia-plugins`. The shared
parent directory is removed only when it becomes empty, so unrelated plugins
stay in place. When the oldest backup contains a pre-rice `config.toml`,
uninstall restores it instead. A hand-written file without the rice marker is
left untouched, and unrelated Noctalia files such as `media.json` stay in place.
Backups and wallpapers are never deleted.

## Current Limitations

- The Luau plugins follow the documented Noctalia plugin API, but their runtime
  behavior still needs verification on a live Noctalia 5.5 or newer session.
- `rice quickstart` uses the Private startup set when Private is active and the
  Work autostart set when Work is active. The two sets are intentionally
  different concepts; see [Startup](STARTUP.md).
- `rice arrange` needs the rice daemon and KWin's scripting D-Bus API. Without a
  running daemon the command fails with one error line.
- The local web configurator is Plan 3 and is not implemented. Edit the TOML
  file and run `rice apply` in the current iteration.
- Noctalia controls the shell; rice does not theme the login screen or the boot
  splash.
- The media plugin expects an external compatible service and does not download
  or scrape media on its own.

## Verifying The Shell

```bash
rice apply
rice doctor
noctalia msg config-reload
systemctl --user status rice-daemon.service rice-shortcuts.service
```

Then check the bar actions, the cheatsheet panel, and the theme panel. A plugin
that does not appear is usually not installed under
`$XDG_DATA_HOME/noctalia-plugins` or not referenced by the generated config.
See [Troubleshooting](TROUBLESHOOTING.md) for the diagnostic sequence.
