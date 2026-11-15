---
status: in-development
progress: 75
version: "0.1.0"
tags: [kde, plasma, kwin, noctalia, arch, cachyos, installer, rice]
scope: "Path-neutral Arch/CachyOS KDE Plasma 6 + Noctalia work/private rice installer with configurable output roles, zones, startup, and autostart."
last_updated: "2026-11-15"
next_steps:
  - Review and integrate the core branch
  - Verify the installer on a clean Arch/CachyOS target
  - Build the Noctalia bar/plugin port and KWin shortcut bindings
  - Build the local web configurator with canvas zones and apply/backup
  - Resolve admin-only KWin blur and login/Plymouth work separately
---

# Current State

- Core backend, installer, generated artifacts, docs, tests, and MIT license are implemented on `feat/core`.
- Full suite: 105 tests passing; integration dry-run and PII gates green.
- Installer has not yet been exercised on a clean target; live rice is unchanged.
- No remote or public push yet. Noctalia bar/plugins and the web configurator remain follow-up plans.
