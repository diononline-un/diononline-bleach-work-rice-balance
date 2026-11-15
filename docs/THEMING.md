# Theming

The theme engine selects wallpapers from a directory you own and applies the
same image to every configured output. It never downloads, scrapes, or stores
image files in the repository.

## Configuration

```toml
[theme]
wallpaper_dir = "$HOME/Pictures/rice-wallpapers"
outputs = ["DP-1", "HDMI-A-1"]
same_image_all_outputs = true
rotation = "hourly"
pause_on_fullscreen = true
pause_on_idle = true
```

| Key | Behavior |
| --- | --- |
| `wallpaper_dir` | Directory scanned for supported images. `$HOME` and environment variables are expanded. |
| `outputs` | Connector names that receive the wallpaper. Must be non-empty before a theme command runs. |
| `same_image_all_outputs` | Must be `true`. `false` raises an explicit unsupported error. |
| `rotation` | Records the intended cadence. The generated timer provides the hourly trigger. |
| `pause_on_fullscreen` | Records intent. The current guard always checks fullscreen. |
| `pause_on_idle` | Records intent. The current guard always checks idle. |

Supported file extensions are `.png`, `.jpg`, `.jpeg`, and `.webp`. Files are
ordered by name. Other files are ignored.

A directory that does not exist is treated as empty. A rotation command then
fails with a clear "no wallpapers" error rather than silently doing nothing.

## Commands

| Command | Behavior |
| --- | --- |
| `rice theme next` | Apply the next file in sorted order, wrapping to the first. |
| `rice theme previous` | Apply the previous file, wrapping to the last. |
| `rice theme random` | Apply a random file from the directory. |
| `rice theme boot` | Wait for Noctalia, then apply the next file. |
| `rice theme hourly` | Apply the next file unless a pause guard is active. |

Each command calls Noctalia once per configured output:

```text
noctalia msg wallpaper-set <connector> <absolute-file-path>
```

The selected path is written to `$XDG_STATE_HOME/rice/theme-current` using an
atomic replace. The next and previous commands read that marker so a manual
change is respected and the same image is not selected twice in a row.

## Boot Behavior

`rice-theme-boot.service` runs `rice theme boot` once after the graphical
session and the rice daemon. The command:

1. Verifies that the wallpaper directory contains supported files.
2. Probes `noctalia msg status` up to 60 times with one-second pauses.
3. Applies the next wallpaper whether or not Noctalia became ready.

The wait exists because the graphical session can start Noctalia after the
service begins. A missing wallpaper set makes the one-shot unit fail; create the
directory and add images, then run `rice theme boot` manually.

## Hourly Rotation

`rice-theme-hourly.timer` triggers `rice-theme-hourly.service` on an hourly
calendar with `Persistent=true`. The service runs `rice theme hourly`.

Before rotating, the guard checks:

1. `org.rice.Rice.FullscreenActive` on the session bus, which the KWin script
   updates when a window goes fullscreen.
2. `org.freedesktop.ScreenSaver.GetActive`, which also covers a locked session.
3. `loginctl show-session <id> -p IdleHint`, when a session id is available.

If any check reports active, the rotation is skipped and the current wallpaper
stays. The two configuration booleans document intended behavior; the current
engine does not disable either check.

## Enabling The Theme Units

`rice apply` enables `rice-daemon.service` and `rice-startup.service`. It
generates but does not enable the boot and hourly theme units. Enable them once:

```bash
systemctl --user enable --now rice-theme-boot.service
systemctl --user enable --now rice-theme-hourly.timer
```

Inspect them with:

```bash
systemctl --user list-timers 'rice-*'
journalctl --user -u rice-theme-hourly.service -b
```

## Wallpaper Policy

The repository ships metadata only. `assets/wallpapers/manifest.toml` records
attribution and optional integrity hashes for files that live in your own
directory. No image binary is committed, and the privacy test asserts that the
asset directory contains nothing except the manifest. See
[Assets](ASSETS.md).

The intended workflow is:

1. Choose images you created, images under a permissive license, or images you
   are allowed to use privately.
2. Put them in the configured directory.
3. Optionally add metadata entries for attribution.
4. Run `rice theme next` or enable the timer.

## Limitations

- Every output receives the same image. Per-output wallpaper sets are not
  implemented and `same_image_all_outputs = false` is rejected.
- Animated or video wallpaper files are not supported.
- Fade or transition settings are not part of the current core.
- `rice apply` does not enable the theme units, as described above.
- The generated Noctalia include covers widget anchors, not theme colors or
  bar styling.
- The future shell port may add a theme panel; the current controls are the CLI
  commands listed on this page.
