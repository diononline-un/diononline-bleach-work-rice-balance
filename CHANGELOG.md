# Changelog

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
