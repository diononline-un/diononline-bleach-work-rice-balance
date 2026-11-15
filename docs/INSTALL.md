# Installation

This page covers the supported install path, the choices the installer accepts,
what it changes on disk, and how to recover or remove an installation.

## Prerequisites

| Requirement | Details |
| --- | --- |
| Distribution | Arch Linux or CachyOS. The preflight accepts `ID` or `ID_LIKE` values `arch`, `archlinux`, or `cachyos` from `/etc/os-release`. |
| Desktop | KDE Plasma 6 with KWin, running in a Wayland or X11 session. |
| Shell | Noctalia 5.5 or newer. The installer installs the package; it does not need to exist before the preflight. |
| AUR helper | `paru` or `yay`. Required for Noctalia and several optional applications. |
| Python | Python 3.11 or newer on `PATH`. |
| Display tooling | `kscreen-doctor` and `qdbus6` from the Plasma session. |
| Session bus | A user D-Bus session, which Plasma provides. |

The preflight probes `plasmashell --version`, the graphical session variables,
and the distribution identifier. The installer then resolves the AUR helper. It
stops before package work if any check fails, so a failed preflight does not
leave a partial installation.

## Clone And Run

```bash
git clone https://github.com/diononline-un/diononline-bleach-work-rice-balance.git
cd diononline-bleach-work-rice-balance
./install.sh --dry-run
./install.sh
```

`install.sh` is a thin bootstrap. It ensures `python-tomli-w` is importable,
adds the checkout `src` directory to `PYTHONPATH`, and runs the Python installer.
The script does not require a virtual environment.

## Installer Choices

The installer takes one variant per application slot and on/off flags for
optional applications. Unspecified flags use the defaults below, so a plain
`./install.sh` is non-interactive and reproducible.

| Flag | Values | Default |
| --- | --- | --- |
| `--work-browser` | `chrome`, `firefox` | `firefox` |
| `--private-browser` | `brave`, `chromium` | `chromium` |
| `--claude` | `desktop`, `code` | `desktop` |
| `--terminal` | `alacritty`, `kitty` | `alacritty` |
| `--youtube-music` | on/off flag | off |
| `--steam` | on/off flag | off |
| `--discord` | on/off flag | off |
| `--opencode` | on/off flag | off |
| `--gpu-recorder` | on/off flag | off |
| `--dry-run` | print actions only | off |
| `--uninstall` | remove installed artifacts | off |

The catalog lives in `defaults/apps.toml`. Each variant declares its Arch package,
argv command, KWin window class, and the activities it belongs to. Commands are
argv arrays and never pass through a shell.

## What The Installer Changes

1. Runs the host preflight and resolves `paru` or `yay`.
2. Plans packages: the base set plus the packages for the selected variants.
3. Installs official packages with `pacman` and helper-only packages with the
   AUR helper. Both calls use `--needed --noconfirm`.
4. Copies the runtime tree to `$XDG_DATA_HOME/rice/` and writes the installed
   `rice` wrapper to `$HOME/.local/bin/rice`.
5. Detects outputs with `kscreen-doctor -j`, picks a layout preset, resolves the
   Private and Work activities, and builds a complete configuration.
6. Writes `$XDG_CONFIG_HOME/rice/rice.toml` atomically.
7. Runs the apply pipeline, which writes generated artifacts, reloads KWin,
   reloads Noctalia, and enables the user units.

Installed runtime paths:

| Path | Content |
| --- | --- |
| `$XDG_DATA_HOME/rice/src/rice` | Python package used by the installed wrapper. |
| `$XDG_DATA_HOME/rice/templates` | KWin, Noctalia, and systemd templates. |
| `$XDG_DATA_HOME/rice/defaults` | Canonical config, app catalog, layout presets. |
| `$XDG_DATA_HOME/rice/assets` | Wallpaper metadata manifest. |
| `$HOME/.local/bin/rice` | Installed CLI wrapper. |
| `$XDG_CONFIG_HOME/rice/rice.toml` | User configuration. |

If the repository contains a `plugins/` directory, each child directory is
copied to `$XDG_DATA_HOME/noctalia-plugins/`. The current core does not ship
plugins; that directory is reserved for the future shell port.

## Dry Run

`./install.sh --dry-run` performs the read-only work but no mutation:

- preflight and AUR helper lookup still run,
- package commands are printed instead of executed,
- no runtime tree, wrapper, configuration, or generated artifact is written,
- activities are looked up but not created.

`rice apply --dry-run` is the narrower check. It validates the configuration and
builds the complete artifact plan without writing or reloading anything. The
current CLI does not render that plan to the terminal; the integration test
inspects it through `ApplyResult.changed`. See
[Troubleshooting](TROUBLESHOOTING.md#rice-apply---dry-run-prints-nothing).

## Backups And Recovery

Before replacing a file, apply copies the existing version to
`$XDG_STATE_HOME/rice/backups/<timestamp>/`. Backups are flat copies named after
the original file, so a Noctalia include and a generated unit are easy to find.

To restore a file manually:

```bash
ls "$XDG_STATE_HOME/rice/backups"
cp "$XDG_STATE_HOME/rice/backups/<timestamp>/rice.toml" \
   "$XDG_CONFIG_HOME/noctalia/rice.toml"
rice apply
```

Backups survive uninstallation on purpose. Remove old backup directories
yourself when they are no longer useful.

If a run is interrupted, rerun `rice apply`. Generated files are written to a
temporary file in the destination directory and renamed into place, so a partial
file is not left behind for a single artifact. A failed reload command is
reported but does not roll back already written files; rerun the command or the
whole apply after fixing the cause.

## Uninstall

```bash
./uninstall.sh
./uninstall.sh --dry-run
```

Uninstall disables the rice user units and removes only artifacts the installer
created:

- `$XDG_DATA_HOME/rice`
- `$XDG_CONFIG_HOME/rice/rice.toml`
- `$XDG_CONFIG_HOME/noctalia/rice.toml`
- `$XDG_CONFIG_HOME/systemd/user/rice-*`
- `$XDG_DATA_HOME/kwin/scripts/rice-placement`
- `$XDG_STATE_HOME/rice/runtime.json`
- `$XDG_STATE_HOME/rice/theme-current`
- `$HOME/.local/bin/rice`, and only when the file contains the rice CLI marker

It keeps your wallpapers, apply backups, unrelated Noctalia configuration,
unrelated systemd units, and unrelated KWin scripts.

## Development Install

For working on the backend without touching the installed runtime:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest tomli-w dbus-python PyGObject
PYTHONPATH=src .venv/bin/python -m rice.cli --version
.venv/bin/python -m pytest
```

The checkout wrapper works the same way:

```bash
PYTHONPATH=src bin/rice doctor
```

Run the shell syntax check after editing the wrappers:

```bash
bash -n install.sh uninstall.sh bin/rice
```

## Next Steps

- Read [Configuration](CONFIGURATION.md) before editing `rice.toml`.
- Read [Placement](PLACEMENT.md) to map outputs and zones.
- Read [Startup](STARTUP.md) to separate login apps from per-activity apps.
- Run `rice doctor` after any session or driver change.
