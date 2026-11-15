# Troubleshooting

Start with the diagnostics the project provides:

```bash
rice doctor
rice apply --dry-run
systemctl --user status rice-daemon.service
journalctl --user -u rice-daemon.service -b
```

`rice doctor` checks that Noctalia and `qdbus6` exist, that at least one output
is detected, and that the configuration loads and validates. It prints one
problem per line and exits non-zero when anything fails.

## Installation

### The installer refuses the distribution

The preflight accepts `arch`, `archlinux`, or `cachyos` from `ID` or `ID_LIKE`
in `/etc/os-release`. Other distributions are not supported by the core. Do not
edit the check to force an install on an unsupported base; package names and
session assumptions differ.

### The installer reports no graphical session

Run the installer from inside a KDE Plasma 6 session. The check accepts
`XDG_SESSION_TYPE=wayland`, `XDG_SESSION_TYPE=x11`, `WAYLAND_DISPLAY`, or
`DISPLAY`. A console login or a bare TTY does not qualify.

### The installer stops for a missing AUR helper

Install `paru` or `yay` first. The installer does not bootstrap a helper because
that would require building untrusted code before the user has reviewed the
process. After installing a helper, rerun `./install.sh`.

### `plasmashell --version` fails

The Plasma shell is missing from `PATH` or the session is not a Plasma session.
Confirm the Plasma 6 packages and start the correct session at the display
manager.

### Package installation fails midway

The installer runs `pacman` and the AUR helper with `--needed --noconfirm`.
Typical causes are a stale package database, a partial upgrade, or a helper that
needs interactive review. Update the system, fix the helper, then rerun the
installer. A rerun is safe: existing files are backed up before replacement.

## Outputs And Placement

### `rice doctor` says no outputs were detected

Check the display session first:

```bash
kscreen-doctor -j
```

The parser keeps only outputs that are both connected and enabled. A disabled
output is ignored by design. Enable it in Plasma's display settings, then rerun
the installer or edit the output list in `rice.toml`.

### Windows do not move to zones

Work through these checks in order:

1. Confirm the KWin script exists at
   `$XDG_DATA_HOME/kwin/scripts/rice-placement/contents/code/main.js`.
2. Confirm the script is enabled:
   `kwriteconfig6 --file kwinrc --group Plugins --key rice-placementEnabled true`
   followed by `qdbus6 org.kde.KWin /KWin reconfigure`.
3. Compare the app's real window class with `wm_class` in `rice.toml`. A rule
   with the wrong class never matches. Case does not matter, but spelling does.
4. Check that the placement activity matches the current activity. A Work rule
   does nothing while Private is active.
5. Confirm the rule zone id exists and the zone belongs to the intended output.
6. Confirm the output connector name still exists. A renamed connector skips
   that rule without stopping the app.

A placement with neither `wm_class` nor `match_title` never matches by design.

### A window is placed but the size is wrong

`gap_px` is subtracted twice from the zone width and height. A large gap on a
narrow zone can collapse the target rectangle; the script enforces a minimum
window size, which may overflow the zone. Reduce the gap or widen the zone.

### Windows move back after manual changes

The script remembers placed windows per activity. It places a window once when
it first matches. If a window is reopened, it is treated as new and placed
again. Adjust the rule if a window should be left alone.

## Noctalia

### `noctalia` is not found

Install the Noctalia package and confirm `noctalia` is on `PATH`. `rice doctor`
reports this explicitly.

### The generated widget anchors do not appear

1. Confirm `$XDG_CONFIG_HOME/noctalia/rice.toml` exists after apply.
2. Run `noctalia msg config-reload`.
3. Confirm each widget zone exists and that output `x`, `y`, `width`, and
   `height` values are real. The bare default configuration has no geometry, so
   anchors land at the output origin.
4. Confirm the widget type name is valid for your Noctalia version.

### Noctalia reload fails

Apply treats reload as best effort and continues. Run the command manually to
see the error:

```bash
noctalia msg config-reload
```

A stale Noctalia process or a syntax error in an unrelated Noctalia file can
make the reload fail. Validate the generated include with a TOML parser if you
edited it by hand; do not edit it manually, because the next apply replaces it.

## User Units

### A rice unit is not running

```bash
systemctl --user status rice-daemon.service
systemctl --user status rice-startup.service
systemctl --user list-unit-files 'rice-*'
journalctl --user -u rice-daemon.service -b
```

`rice apply` runs `daemon-reload` and enables the daemon and startup units. If a
unit file was generated after the last daemon reload, run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now rice-daemon.service rice-startup.service
```

### Theme rotation never runs

`rice apply` generates but does not enable the theme units. Enable them:

```bash
systemctl --user enable --now rice-theme-boot.service rice-theme-hourly.timer
systemctl --user list-timers 'rice-*'
```

Then check the service journal. Rotation also skips while a fullscreen window is
active, the screen is locked, or the session reports idle. This is intentional.

### The daemon starts but D-Bus calls fail

Confirm the bus name is owned:

```bash
busctl --user status org.rice.Rice
```

If the unit is `Type=dbus` and fails immediately, inspect the journal for an
import error. The daemon needs `dbus-python` and `PyGObject`, which the installer
installs as system packages.

## Startup And Autostart

### Applications launch twice

Autostart deduplicates with markers in `$XDG_RUNTIME_DIR/rice/`. Login startup
does not deduplicate manual reruns. If you ran `rice startup` yourself and the
login service also ran it, both launches are expected. Remove the marker only
when you intentionally want an autostart set to run again.

### Autostart does not run when entering an activity

1. Confirm `$XDG_RUNTIME_DIR` is set.
2. Check for `$XDG_RUNTIME_DIR/rice/autostart-<role>.done`. A leftover marker from
   an earlier attempt suppresses the launch until logout.
3. Confirm the activity role exists in `[activities.<role>]` with a resolved
   `kde_id`.
4. Run `rice activity <role>` manually and read the error.

A missing command for a referenced app fails that call instead of launching a
partial set.

### Startup fails after a configuration change

The runtime document is generated, not read from `rice.toml` at launch time.
Rerun `rice apply` after editing the configuration, then retry. Restart the
daemon so it loads the new runtime document.

## Theming

### `rice theme next` reports no wallpapers

The configured directory is missing or contains no supported extensions. Create
it and add `.png`, `.jpg`, `.jpeg`, or `.webp` files. Check the actual path:

```bash
python3 -c 'import json,os; print(json.load(open(os.path.expandvars("$XDG_STATE_HOME/rice/runtime.json")))["theme"]["wallpaper_dir"])'
```

### `same_image_all_outputs = false` is rejected

Per-output wallpaper sets are not implemented. Set the value back to `true`.

### The wallpaper changes on one output only

The engine calls `noctalia msg wallpaper-set` once per connector in
`theme.outputs`. Confirm every connector is listed and still present. A stale
connector name produces a failing call for that output.

## Applying And Recovering

### `rice apply --dry-run` prints nothing

The current CLI validates the configuration and exits without rendering the
artifact plan. This is expected; the plan is available through the Python API
that the integration test uses. To inspect it:

```bash
PYTHONPATH="${XDG_DATA_HOME:-$HOME/.local/share}/rice/src" python3 -c \
  'from rice.apply import apply_config; from rice.paths import config_path; \
print(*apply_config(config_path(), dry_run=True).changed, sep="\n")'
```

A non-zero exit still means validation failed; the error message is printed to
standard error.

### Apply fails validation

The message lists every problem separated by semicolons. Fix the referenced
section and rerun `rice apply --dry-run`. Nothing is written when validation
fails.

### A file was overwritten and I want the previous version

Look in `$XDG_STATE_HOME/rice/backups/`. Each apply creates a timestamped
directory with flat copies of the files it replaced. Copy the file back and run
apply again if needed.

### Apply was interrupted

Rerun `rice apply`. Individual files are written through a temporary file and
renamed, so a single artifact is either old or new. The run as a whole is not a
transaction; revisit the output of the interrupted run before assuming every
file was updated.

### Uninstall left files behind

Uninstall removes only known rice-owned paths. A unit whose name does not start
with `rice-`, a KWin script in another directory, or a wrapper that does not
contain the rice CLI marker is intentionally left alone. Backups and wallpapers
are also kept. Remove those manually after confirming they are not needed.

## Tests

### The privacy test fails

The message names the file and line that matched a personal-data pattern. Remove
the host name, endpoint, private address, or absolute user home path and use an
XDG variable or `$HOME` instead. Do not add an exception for a real value; fix
the value.

### The asset test fails

`assets/wallpapers/` must contain only `manifest.toml`, and each manifest entry
must use exactly the documented keys. Remove any image binary and correct the
entry. See [Assets](ASSETS.md).

### A shell wrapper fails the syntax check

Run:

```bash
bash -n install.sh uninstall.sh bin/rice
```

Fix the reported line, then rerun the check. The wrappers are small bootstraps;
they should contain no interactive prompts.
