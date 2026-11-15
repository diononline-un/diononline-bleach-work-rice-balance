# Changelog

## 2026-11-15 — Optional media plugin

- Added `plugins/media/` as an opt-in `rice/media` companion for a local YouTube Music API; it stays out of the base bar and desktop widgets until the user enables it.
- The plugin reads `api_url` from `$XDG_CONFIG_HOME/noctalia/media.json`, falls back to the previous `http://127.0.0.1:26538/api/v1` default, and tolerates a missing or malformed config.
- Removed the personal `/home/dion` cache fallback; `HOME` is now required and every code path uses `HOME` plus XDG variables.
- Shipped `defaults/noctalia/media.json` with a comment that users must run their own compatible service.
- Added asset checks for the five plugin files, the manifest, the default JSON, and personal-path scans; suite is now 137 tests.
- Translated the remaining German panel strings (tooltips, queue labels, empty and error states) to English and added a regression test, raising the suite to 138 tests.

## 2026-11-15 — Profile and cheatsheet plugins

- Ported the activity switch to `plugins/profile/` as `rice/profile:bar`; it reads activity ids from `$XDG_STATE_HOME/rice/runtime.json` and calls `rice activity work|private` through argv.
- Ported the shortcut reference to `plugins/cheatsheet/` as `rice/cheatsheet:panel` with English group titles and role-neutral screen labels (`Main`, `Side`, `Portrait`) instead of connector names.
- Added `rice cheatsheet`, `rice quickstart` (launches the private startup set or the Work autostart set for the current activity), and `rice arrange` (clear placeholder until the KWin method lands).
- Fixed `_qdbus` so it passes `interface.method` as one token; recent `qdbus6` rejected the split form and `rice activity` failed on the live machine.
- Updated README command table and INSTALL plugin description; suite is now 133 tests.

## 2026-11-15 — Theme CLI parity and theme selector plugin

- Added `rice theme set <path>`, `refresh`, `panel`, and `status`; `set` resolves inside `theme.wallpaper_dir` and rejects paths outside it.
- `refresh` builds `$XDG_CACHE_HOME/rice-theme/index.tsv` atomically with 480x270 JPEG thumbnails and fails clearly when `magick` is missing.
- `panel` toggles `rice/themes:panel` through the same `noctalia msg` status probe the old script used.
- Moved the theme selector to `plugins/themes/` with argv-based `rice theme` calls, `HOME`/XDG lookups, and no machine-specific paths.
- Updated theming and install docs; suite is now 122 tests.
- Caught `subprocess.SubprocessError` in the CLI boundary so failed `magick` or `noctalia` calls report one clean `rice:` line instead of a traceback.

## 2026-11-15 — Core hardening and release hygiene

- Fixed triple-monitor layout selection so side and portrait zones use the two non-primary outputs regardless of KScreen order.
- Added clean CLI error reporting for validation, runtime, and missing-file failures.
- Added the MIT license and tightened the PII gate so application-catalog tests are scanned without whole-file exclusions.
- Removed dead placement ids and unused config imports; hardened widget-anchor defaults.
- Core branch is ready for integration; Noctalia bar/plugins, shortcuts, and the web configurator remain follow-up plans.

## 2026-11-15 — Review fixes for core branch

- Made the triple layout pick the two non-primary outputs by identity and raise `ValueError` when fewer than two exist, so KScreen output order no longer misassigns zones.
- Added a CLI error boundary that prints `rice: <message>` and returns 1 for operational errors instead of a traceback.
- Added the MIT `LICENSE` and removed unused `rice.config` path imports; config path now comes from `rice.paths`.
- Dropped phantom app ids from default placements and made widget anchors default missing zone geometry.
- Tightened the PII gate so `tests/test_apps.py` stays scanned by building its denylist markers through concatenation.

## 2026-11-15 — Core runtime and installer

- Added KWin placement rules, fullscreen reporting, and the `org.rice.Rice` D-Bus daemon.
- Added Noctalia/runtime/systemd generators, atomic apply with backups, startup/autostart, and theme rotation.
- Added the package installer with Arch/CachyOS preflight, initial config generation, dry-run, and uninstall paths.
- Added English installation, configuration, placement, startup, theming, asset, architecture, and troubleshooting docs.
- Added integration and PII coverage; Noctalia bar/plugins and the web configurator remain follow-up plans.

## 2026-11-15 — Application catalog and placements

- Added the generic application catalog with work/private browser choices, Claude, terminals, media, Steam, Discord, OpenCode, and GPU recorder.
- Added stable app-id resolution for installer choices and activity memberships.
- Added default placements for terminal and recorder to the existing layout mappings.
- Package and window-class names remain to be verified during installer integration.

## 2026-11-15 — Core scaffold and config model

- Added the `rice` Python CLI skeleton and development wrapper.
- Added canonical `rice.toml` loading, atomic writing, and relationship validation.
- Added XDG path helpers and a generic default config with no personal paths or wallpaper binaries.
- Added KScreen output detection, Activity Manager helpers, and triple/single-split/ultrawide zone presets.
- Core installer, generators, startup/autostart, theme, and configurator work remain open.
