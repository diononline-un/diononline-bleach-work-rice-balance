# Configuration

The rice is driven by one TOML document:

```text
$XDG_CONFIG_HOME/rice/rice.toml
```

With no XDG override that resolves to `$HOME/.config/rice/rice.toml`. The
canonical template is `defaults/rice.toml` in the repository. `tomllib` reads
the file; `tomli-w` writes it. The installer and any future configurator replace
the file atomically, never as a partial document.

Run `rice apply --dry-run` after an edit to validate the document and list the
artifacts it would produce. Run `rice apply` to write and reload.

## Top-Level Sections

These sections must exist:

```text
[meta] [output] [zone] [app] [placement] [activities]
```

A missing section fails validation with `missing section: <name>`. All reference
errors are collected and reported together, separated by semicolons.

## [meta]

```toml
[meta]
schema_version = 1
```

`schema_version` records the configuration generation. The current core
validates only that the section exists; it does not migrate older documents.

## [[output]]

An output describes a connected display.

```toml
[[output]]
id = "main"
role = "main"
connector = "DP-1"
primary = true
x = 0
y = 0
width = 5120
height = 1440
```

| Key | Meaning |
| --- | --- |
| `id` | Stable internal identifier referenced by zones. Must be present and unique. |
| `role` | Human-readable label such as `main` or `secondary`. The installer writes `main` for the primary output and `secondary` for the rest. The generator does not branch on this field. |
| `connector` | Real KWin output name, for example `DP-1` or `HDMI-A-1`. This is what the generated KWin and Noctalia files use. |
| `primary` | Whether this is the primary display. Used by the installer to choose the main output. |
| `x`, `y` | Output origin in the global virtual desktop. Used for desktop-widget anchors. |
| `width`, `height` | Output pixel geometry. Used for desktop-widget anchors. |

Zones must reference a declared output `id`. If the configured connector is not
present at runtime, the KWin script cannot resolve the output and skips that
rule; applications still launch normally.

## [[zone]]

Zones are rectangles relative to the usable area of one output. The usable area
already excludes exclusive shell reserves such as a top bar.

```toml
[[zone]]
id = "center-left"
output = "main"
kind = "app"
x = 0.0
y = 0.0
w = 0.5
h = 1.0
gap_px = 8
```

| Key | Meaning |
| --- | --- |
| `id` | Stable zone identifier. Must be present and unique. |
| `output` | Declared output `id`. |
| `kind` | `app` for application tiling, `shell` for desktop-widget anchors. |
| `x`, `y`, `w`, `h` | Fractions of the usable output area, in the range 0 to 1. |
| `gap_px` | Inset applied inside the zone when a window is placed. |

Validation rules:

- `kind` must be `app` or `shell`.
- `w` and `h` must be positive.
- `x` and `y` must not be negative.
- `x + w <= 1` and `y + h <= 1`.

Overlapping app zones are allowed. Placement priority decides which rule wins.
Shell zones are anchors for desktop widgets and are not application placement
targets.

## [[app]]

An application entry is a launchable command plus the metadata placement needs.

```toml
[[app]]
id = "work-browser"
name = "Work Browser"
command = ["firefox"]
wm_class = "firefox"
package = "firefox"
optional = true
activities = ["work"]
```

| Key | Meaning |
| --- | --- |
| `id` | Stable identifier referenced by placement, startup, and autostart. Must be present and unique. |
| `name` | Display name. |
| `command` | Non-empty argv array of non-empty strings. It is executed directly, never through a shell. |
| `wm_class` | KWin window class used for matching. Compared case-insensitively. |
| `package` | Arch package name used by the installer plan. |
| `optional` | Whether the package is an optional choice. |
| `activities` | Activity roles this app belongs to. Used to derive default placements. |

The installer resolves catalog choices into app ids such as `work-browser`,
`private-browser`, `claude`, `terminal`, `youtube-music`, `steam`, `discord`,
`opencode`, and `gpu-recorder`.

## [[placement]]

A placement binds an application to a zone inside an activity.

```toml
[[placement]]
app = "work-browser"
activity = "work"
zone = "center-left"
mode = "normal"
priority = 10
match_title = ""
```

| Key | Meaning |
| --- | --- |
| `app` | Declared app `id`. |
| `activity` | Declared activity role key. |
| `zone` | Declared zone `id`. |
| `mode` | `normal`, `maximized`, or `fullscreen`. |
| `priority` | Optional integer. Higher values are considered first. |
| `match_title` | Optional case-insensitive substring of the window title. |

Validation checks that every reference exists and that the mode is supported.
The generator builds rules in this order:

1. Highest `priority` first.
2. On equal priority, the later placement in the file wins.

KWin matches a window by lowercased window class, then by the optional title
substring, and only while the placement activity is current. A rule with an
empty activity id matches every activity.

## [activities.<role>]

```toml
[activities.private]
name = "Private"
kde_id = ""

[activities.work]
name = "Work"
kde_id = ""
```

`name` is the display name used when the installer looks up or creates the KDE
activity. `kde_id` is the resolved activity UUID. The installer writes it; an
empty value means the activity has not been resolved yet. No UUID is committed
to the repository.

Autostart sections must use a role that exists here.

## [startup]

Login-time application sets:

```toml
[startup]
always = ["gpu-recorder"]
private = ["private-browser", "terminal"]
```

`always` launches at every login. `private` launches at login as the Private
set; the current core does not inspect which activity Plasma restored. Both
lists must reference declared app ids. See [Startup](STARTUP.md) for the exact
launch sequence and the initial-activity limitation.

## [autostart.<role>]

First-entry application sets, one section per activity:

```toml
[autostart.private]
apps = []

[autostart.work]
apps = ["work-browser", "claude"]
```

Each `apps` list must reference declared app ids. A role without a matching
`[activities.<role>]` section fails validation.

## [[desktop_widget]]

Desktop widgets are anchored to shell zones:

```toml
[[desktop_widget]]
plugin = "clock"
zone = "edge-right"
scale = 1.0
```

| Key | Meaning |
| --- | --- |
| `plugin` | Noctalia widget type written as the generated `type`. |
| `zone` | Shell zone whose center becomes the widget anchor. |
| `scale` | Scale factor passed to Noctalia. |

The anchor is computed in absolute output coordinates from the zone center. The
output is derived from the zone; a separate `output` key is not read by the
current generator. Generated widget keys use the `rice_` prefix so unrelated
Noctalia widgets are not overwritten.

## [theme]

`defaults/rice.toml` does not ship a `[theme]` table. The installer injects it
when it builds the initial configuration. If you edit the canonical config by
hand, add the table before running theme commands.

```toml
[theme]
wallpaper_dir = "$HOME/Pictures/rice-wallpapers"
outputs = ["DP-1", "HDMI-A-1"]
same_image_all_outputs = true
rotation = "hourly"
pause_on_fullscreen = true
pause_on_idle = true
```

| Key | Meaning |
| --- | --- |
| `wallpaper_dir` | Directory scanned for `.png`, `.jpg`, `.jpeg`, and `.webp` files. |
| `outputs` | Connector names that receive the wallpaper. Must be non-empty for a theme command. |
| `same_image_all_outputs` | Only `true` is supported in the current core. |
| `rotation` | Recorded rotation intent. The generated timer drives hourly rotation. |
| `pause_on_fullscreen` | Recorded guard intent for the theme engine. |
| `pause_on_idle` | Recorded guard intent for the theme engine. |

The current engine always applies both fullscreen and idle guards. The two
boolean keys document intent and are available to the future UI. See
[Theming](THEMING.md).

## Validation Summary

The validator checks:

- required top-level sections,
- presence and uniqueness of output, zone, and app ids,
- zone output references, zone kinds, positive size, and 0-to-1 bounds,
- placement app, zone, activity, and mode references,
- app commands are non-empty argv arrays,
- startup and autostart app references,
- autostart roles have a matching activity.

A failed validation raises before any file is written or any reload command is
run.

## Environment Variables

| Variable | Default | Used for |
| --- | --- | --- |
| `XDG_CONFIG_HOME` | `$HOME/.config` | Configuration and systemd user units. |
| `XDG_DATA_HOME` | `$HOME/.local/share` | Installed runtime tree and KWin script. |
| `XDG_STATE_HOME` | `$HOME/.local/state` | Runtime JSON, theme marker, and backups. |
| `XDG_RUNTIME_DIR` | set by the session | Per-session startup and autostart markers. |

No absolute user home path is stored in the repository or in generated files.
