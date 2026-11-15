# Changelog

## 2026-11-15 — Configurator save backups and widget validation

- Save and restore now copy the previous `rice.toml` into `$XDG_STATE_HOME/rice/web-backups/<stamp>` before every successful write, reusing the backup timestamp/collision logic; no-op and invalid writes create no backup, and a failed write rolls the fresh backup back and returns JSON 500 instead of dropping the connection.
- Removing a zone in `src/web/app.js` now also prunes `desktop_widget` entries that reference it, matching the placement cleanup.
- `validate_config` rejects a `desktop_widget` that is not a list, has an empty `plugin`, or references an unknown zone, so an invalid document cannot be saved.
- JSON request bodies are capped at 2 MiB with a 413 response.
- Docs updated in `docs/CONFIGURATOR.md` and `docs/CONFIGURATION.md`. Suite is now 221 tests.

## 2026-11-15 — Configurator packaging, docs, and PR

- `install_tree` now copies `src/web` to `$XDG_DATA_HOME/rice/src/web` and writes an installed `rice-config` launcher next to `rice`; both launchers resolve the runtime through `$XDG_DATA_HOME` instead of the checkout path.
- Uninstall removes each launcher only when its rice module marker is present, so a user-owned `rice` or `rice-config` file survives, and the installed web assets leave with `$XDG_DATA_HOME/rice`.
- Added installer tests for web assets, both launchers, installed `WEB_ROOT`/catalog resolution, dry-run behavior, and ownership-aware launcher removal.
- Added `docs/CONFIGURATOR.md` (start command, token and loopback model, tabs, canvas, validate/save/apply, backup/restore, API, limitations) and linked it from the README.
- README, `docs/INSTALL.md`, and `docs/ARCHITECTURE.md` describe `rice config`/`rice-config`, the web assets, and the installed paths; `PROJECT_STATUS.md` marks Plan 3 implemented with live verification still open.
- PII scan now covers `.html` and `.css` and asserts the web assets are scanned. Suite is 210 tests.

## 2026-11-15 — Structured config editors and apply errors

- Apps, Placement, Startup, Autostart, Widgets, Theme, and Outputs tabs now edit `state.config` in place: tables with add/remove rows, selects limited to the configured apps/activities/zones, checkbox lists for startup and autostart, and lazy creation of the `[theme]` table.
- Apps edit id, name, comma-separated argv, window class, and activities; removing an app also drops its placement, startup, and autostart references.
- Outputs get a role select (`main`/`side`/`portrait`/`custom`) plus a custom-role field and primary toggle; connectors stay read-only and come from the saved config and detected displays, never a fixed list.
- Theme gains a wallpaper directory input, a multi-select built from configured and detected connectors, rotation intent, and the same-image/fullscreen/idle flags.
- Save and Apply now surface PUT validation errors and apply-run failures in the Apply tab and status bar; API errors carry their payload, and Apply still PUTs the config before POSTing `/api/apply`.
- Replaced the JSON widget/theme editors with the structured forms; removed the JSON editor CSS and added form/table field styles. Suite is now 203 tests.

## 2026-11-15 — Canvas zone editor

- Layout tab now renders one aspect-correct canvas per configured output, using detected width/height when available and 16:9 otherwise; each canvas carries its own accessible label and zones.
- Zones drag with pointer events and resize through a `.resize-zone` corner handle; geometry snaps to 0.01, clamps to `[0,1]`, enforces a 0.05 minimum, and keeps `x+w`/`y+h` inside the canvas.
- Added a selected-zone card with `add-zone`/`remove-zone` buttons, kind and gap readout; adding creates a unique `custom-<n>` app zone on the selected output, removing confirms first and drops dependent placement rows.
- All edits mutate `state.config` only and mark the document dirty; no API call happens until Save or Apply.
- Added three web asset tests, including drag/resize/add/remove tokens and a per-output canvas check. Suite is now 194 tests.

## 2026-11-15 — Configurator shell and tabs

- Added `src/web/index.html`, `src/web/style.css`, and `src/web/app.js`: dark responsive shell with tabs Apps, Outputs, Layout, Placement, Startup, Autostart, Widgets, Theme, and Apply.
- `app.js` reads the session token from `?token=`, keeps it in session storage, strips it from the address bar, and sends `Authorization: Bearer` on every API call.
- Startup loads `/api/state`; tabs show read-only summaries plus JSON editors for widgets and theme. Layout shows a zone preview with selection, ready for canvas editing.
- Validate, Save, and Apply call `/api/validate`, `PUT /api/config`, and `/api/apply`; buttons disable while busy and a `beforeunload` guard warns about unsaved edits.
- Replaced the Task 1 "assets absent" check with a static-asset serving test now that the UI exists.
- Suite is now 191 tests.

## 2026-11-15 — Local web configurator API

- Added `src/rice/web.py`: a loopback `ThreadingHTTPServer` exposing `/api/health`, `/api/state`, `/api/outputs`, `/api/config`, `/api/validate`, `/api/apply`, `/api/backup`, and `/api/restore`, all gated by a `Bearer` token with `hmac.compare_digest`.
- Config writes go through the existing atomic `save_config`; apply is the only action and runs the injected `apply_func`, so the API never shells out.
- Backups land under `$XDG_STATE_HOME/rice/web-backups/<timestamp>/rice.toml`; restore only accepts paths inside that root.
- Added `rice config` (`--no-browser`) and the `bin/rice-config` wrapper, both lazy-importing web so CLI help never loads dbus.
- Suite is now 183 tests.

## 2026-11-15 — Shortcut cleanup and cheatsheet sync

- Switched `rice shortcuts disable-conflicts` to the Plasma 6 `setForeignShortcutKeys` call (2-element action id plus an empty `a(ai)` key list), keeping a `setForeignShortcut` fallback for older Plasma and a concise stderr warning when retries fail.
- Rewrote the cheatsheet panel to list only the generated bindings with neutral labels; removed stale keys, the personal terminal names, and the media rows.
- Aligned the cheatsheet panel width with its manifest and the profile widget with the qualified `org.kde.ActivityManager.Activities.CurrentActivity` call.
- Annotated the core-design spec where it still described the old `noctalia/rice.toml` include; the branch now merges `$XDG_CONFIG_HOME/noctalia/config.toml`.
- Suite is now 167 tests.

## 2026-11-15 — Installer roles, Noctalia docs, and privacy coverage

- Fixed installer output roles: the primary display is `main`, the first non-primary is `side`, and the second is `portrait`, independent of KScreen order; ids and geometry stay unchanged.
- Added installer coverage that copies all four plugin manifests and the Noctalia base config, removes rice-owned plugin directories on uninstall, and restores the oldest pre-rice `config.toml` when one exists.
- Hardened plugin ownership: every installed plugin directory gets a `.rice-plugin` marker, install refuses an unmarked pre-existing directory with the conflicting path, and uninstall removes only marked directories.
- Added `docs/NOCTALIA.md` and `docs/SHORTCUTS.md`; refreshed README, install, architecture, placement, theming, and troubleshooting text away from the old include path.
- Extended the PII scan to `.luau` and JSON sources and fixed the skip check so worktree runs scan the real tree; removed the remaining personal path from the changelog and test assertion.
- Suite is now 162 tests.

## 2026-11-15 — KWin shortcuts, bar actions, and arrange

- Generated the KWin shortcut block from the config; move targets resolve by output role (`main`/`side`/`portrait`) instead of hard-coded connector names, and every daemon call uses `org.rice.Rice`.
- Added `rice arrange`, which re-applies the layout by loading a generated one-shot `arrange.js` through KWin's scripting D-Bus API, backed by the daemon `ReapplyPlacement` method.
- Added daemon methods `QuickstartWork`/`QuickstartPrivate`/`QuickstartCurrent`, `ToggleCheatSheet`, and `OpenTerminal`/`OpenAnimatedTerminal`; terminals launch from the runtime app catalog with no hard-coded command.
- Added `rice shortcuts disable-conflicts` plus the generated `rice-shortcuts.service` unit to clear colliding KDE global shortcuts at login.
- Suite is now 153 tests.

## 2026-11-15 — Optional media plugin

- Added `plugins/media/` as an opt-in `rice/media` companion for a local YouTube Music API; it stays out of the base bar and desktop widgets until the user enables it.
- The plugin reads `api_url` from `$XDG_CONFIG_HOME/noctalia/media.json`, falls back to the previous `http://127.0.0.1:26538/api/v1` default, and tolerates a missing or malformed config.
- Removed the personal hard-coded cache fallback; `HOME` is now required and every code path uses `HOME` plus XDG variables.
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

## 2026-11-15 — Optional KWin appearance profile

- Added `rice appearance apply/status/remove` for backed-up, rice-owned KWin opacity rules.
- Added active/inactive opacity profiles for browsers, editors, Claude, chat, file manager, and media apps.
- Added fullscreen and Steam/gamescope opacity exceptions; terminal opacity stays native.
- Documented whole-window transparency limits and the interaction with KWin blur.
