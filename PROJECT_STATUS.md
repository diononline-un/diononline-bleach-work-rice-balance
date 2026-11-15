---
status: in-development
progress: 98
version: "0.1.0"
tags: [kde, plasma, kwin, noctalia, arch, cachyos, installer, rice, configurator]
scope: "Path-neutral Arch/CachyOS KDE Plasma 6 + Noctalia work/private rice installer with configurable output roles, zones, startup, autostart, and a local web configurator."
last_updated: "2026-11-15"
next_steps:
  - Verify the Luau plugins, bar actions, and KWin shortcuts on the live desktop
  - Verify the installer and uninstall restore path on a clean Arch/CachyOS target
  - Verify the configurator canvas, save, and apply flow in a real browser
  - Review and merge PR #1 for feat/noctalia-ui and the configurator PR
  - Resolve admin-only KWin blur and login/Plymouth work separately
---

# Current State

- Core backend, installer, generated artifacts, docs, tests, and MIT license are implemented on `feat/core`.
- Noctalia UI tasks 1-5 are committed: merged shell config, theme/profile/cheatsheet/media plugins, bar actions, `rice quickstart`, `rice cheatsheet`, `rice arrange`, generated KWin shortcuts, and conflict cleanup.
- Task 6 adds role-based installer output assignment (`main`/`side`/`portrait`), plugin install/uninstall coverage, Noctalia config restore, `docs/NOCTALIA.md`, `docs/SHORTCUTS.md`, and `.luau` PII scanning.
- Plan 3 (web configurator) is implemented: local API, shell, canvas zone editor, structured editors, `rice config`, installed `rice-config`, web assets under `$XDG_DATA_HOME/rice/src/web`, and `docs/CONFIGURATOR.md`.
- Full suite: 210 tests passing; integration dry-run, JS syntax, and PII gates green in the worktree.
- Live verification of the configurator canvas, the Luau plugins, and the installer restore path is still open.
