---
status: in-development
progress: 95
version: "0.1.0"
tags: [kde, plasma, kwin, noctalia, arch, cachyos, installer, rice]
scope: "Path-neutral Arch/CachyOS KDE Plasma 6 + Noctalia work/private rice installer with configurable output roles, zones, startup, and autostart."
last_updated: "2026-11-15"
next_steps:
  - Verify the Luau plugins, bar actions, and KWin shortcuts on the live desktop
  - Verify the installer and uninstall restore path on a clean Arch/CachyOS target
  - Review and merge PR #1 for feat/noctalia-ui
  - Build the local web configurator with canvas zones and apply/backup
  - Resolve admin-only KWin blur and login/Plymouth work separately
---

# Current State

- Core backend, installer, generated artifacts, docs, tests, and MIT license are implemented on `feat/core`.
- Noctalia UI tasks 1-5 are committed: merged shell config, theme/profile/cheatsheet/media plugins, bar actions, `rice quickstart`, `rice cheatsheet`, `rice arrange`, generated KWin shortcuts, and conflict cleanup.
- Task 6 adds role-based installer output assignment (`main`/`side`/`portrait`), plugin install/uninstall coverage, Noctalia config restore, `docs/NOCTALIA.md`, `docs/SHORTCUTS.md`, and `.luau` PII scanning.
- Full suite: 167 tests passing; integration dry-run and PII gates green in the worktree.
- The optional `rice/media` plugin stays disabled until a user configures a local compatible media API.
- Installer and Luau behavior still need live verification; `feat/noctalia-ui` is pushed for review but not merged.
- Plan 3 (web configurator) remains open; the project is not done.
