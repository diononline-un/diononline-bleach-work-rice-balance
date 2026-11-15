# Bleach Work/Private Rice Balance

A configurable KDE Plasma 6 and Noctalia desktop layout for Arch-based systems.
One TOML configuration describes displays, tiling zones, applications,
activities, startup sets, and wallpapers; the core backend generates every KWin,
Noctalia, systemd, and runtime file from that document.

The project is split into three plans. This repository contains the core
backend from plan one and the Noctalia shell port from plan two. The Noctalia
bar, four plugins, generated shortcuts, and bar actions are implemented; live
verification on a target desktop is pending. The local web configurator is
plan three and is not implemented here.

## What It Does

- Separate Work and Private application sets with one shared zone layout.
- Configurable output roles, zone geometry, and placement rules.
- Triple-monitor, ultrawide, and single-split layout presets.
- Generated KWin placement script, merged Noctalia configuration, systemd
  units, and runtime configuration.
- A Noctalia bar with rice actions, a theme selector, a Work/Private indicator,
  and a shortcut cheatsheet, plus an optional media plugin.
- Generated KWin shortcuts that resolve window-move targets by output role.
- Startup (login) and autostart (first activity entry) as separate concepts.
- Wallpaper rotation from a user-supplied directory with fullscreen and idle
  guards.
- Timestamped backups of existing generated files before replacement.
- No bundled third-party wallpapers and no personal host or credential data.

## Requirements

- Arch Linux or CachyOS with `pacman`.
- KDE Plasma 6 with KWin, inside an active graphical session.
- Noctalia 5.5 or newer.
- `paru` or `yay` for packages that are not in the official repositories.
- Python 3.11 or newer.

The installer adds the Python runtime packages it needs. It never bootstraps an
AUR helper; if neither helper is present it stops and tells you what to install.

## Install

```bash
git clone https://github.com/diononline-un/diononline-bleach-work-rice-balance.git
cd diononline-bleach-work-rice-balance
./install.sh
```

Preview the full install without changing packages or files:

```bash
./install.sh --dry-run
```

After installation the `rice` wrapper lives in `$HOME/.local/bin/rice`. Verify
the session and the generated plan:

```bash
rice doctor
rice apply --dry-run
rice apply
```

## Everyday Commands

| Command | Purpose |
| --- | --- |
| `rice apply` | Regenerate artifacts from the current configuration and reload the desktop. |
| `rice apply --dry-run` | Validate the configuration and write nothing. |
| `rice doctor` | Check Noctalia, D-Bus tooling, outputs, and configuration validity. |
| `rice startup` | Launch the login startup sets once. |
| `rice activity private` | Switch to the Private activity and run its autostart set once. |
| `rice activity work` | Switch to the Work activity and run its autostart set once. |
| `rice theme next` | Apply the next wallpaper in sorted order. |
| `rice theme previous` | Apply the previous wallpaper. |
| `rice theme random` | Apply a random wallpaper from the configured directory. |
| `rice cheatsheet` | Toggle the shortcut cheatsheet panel. |
| `rice quickstart` | Launch the app set that belongs to the current activity. |
| `rice arrange` | Reapply the window layout through the daemon and KWin. |
| `rice shortcuts disable-conflicts` | Clear KDE shortcuts that collide with the rice bindings. |
| `rice daemon` | Run the user D-Bus daemon in the foreground. |

## Documentation

- [Installation](docs/INSTALL.md): prerequisites, choices, dry-run, recovery.
- [Configuration](docs/CONFIGURATION.md): every TOML section and validation rule.
- [Architecture](docs/ARCHITECTURE.md): modules, data flow, generated artifacts.
- [Placement](docs/PLACEMENT.md): outputs, zones, presets, and ultrawide layout.
- [Startup](docs/STARTUP.md): login startup versus per-activity autostart.
- [Theming](docs/THEMING.md): wallpaper rotation, guards, and generated units.
- [Noctalia](docs/NOCTALIA.md): merged config, bar, plugins, and media setup.
- [Shortcuts](docs/SHORTCUTS.md): bindings, output roles, and conflict cleanup.
- [Assets](docs/ASSETS.md): metadata-only wallpaper policy and manifest format.
- [Troubleshooting](docs/TROUBLESHOOTING.md): common display, Noctalia, and unit issues.

## Repository Layout

```text
.
├── install.sh              installer bootstrap
├── uninstall.sh            removal bootstrap
├── bin/rice                checkout-relative CLI wrapper
├── defaults/               canonical configuration and app catalog
│   ├── rice.toml
│   ├── apps.toml
│   ├── noctalia/           base shell config and optional media JSON
│   └── layouts/            triple, ultrawide, single-split presets
├── docs/                   published English documentation
├── plugins/                themes, profile, cheatsheet, and media plugins
├── src/rice/               core Python backend
├── templates/              KWin, Noctalia, and systemd templates
├── assets/wallpapers/      metadata manifest only, no image files
└── tests/                  unit, integration, and privacy tests
```

## Privacy And Asset Policy

The repository contains no personal host names, remote endpoints, private
network names, credentials, IP addresses, or hard-coded user home paths. Every
path is derived from `$HOME` or the XDG base-directory variables at runtime.

Wallpapers are never committed. `assets/wallpapers/manifest.toml` stores
metadata only: identifier, local file name, public attribution link, artist,
usage terms, and an optional hash. The theme engine reads files from the
directory you configure and never downloads or scrapes images. See
[Assets](docs/ASSETS.md) for the manifest format.

## Current Limitations

- The Noctalia bar, plugins, and shortcuts are generated and installed, but the
  Luau runtime behavior still needs verification on a live Noctalia 5.5 or
  newer session.
- The optional media plugin expects your own compatible local media API; no
  service is bundled.
- The local web configurator is plan three and is not implemented. Edit
  `rice.toml` and run `rice apply` in the current iteration.
- Every output receives the same wallpaper. Per-output wallpaper sets are not
  implemented.
- Animated or video wallpapers are not supported.
- `rice apply` enables the daemon, startup, and shortcut units. The generated
  boot and hourly theme units must be enabled manually if you want automatic
  rotation.
- The login screen and boot splash are not themed; changing them requires
  system-level authentication and is outside this plan.
- Only Arch-based distributions are supported.
- The initial activity at login is whatever Plasma restores. Explicit
  initial-activity selection is planned with the configurator.
