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
  - Finish the Noctalia plugin port and verify KWin shortcut bindings
  - Build the local web configurator with canvas zones and apply/backup
  - Resolve admin-only KWin blur and login/Plymouth work separately
---

# Current State

- Core backend, installer, generated artifacts, docs, tests, and MIT license are implemented on `feat/core`.
- Full suite: 121 tests passing; integration dry-run and PII gates green.
- Theme CLI parity and the `rice/themes` picker plugin are implemented on `feat/noctalia-ui`.
- Installer has not yet been exercised on a clean target; live rice is unchanged.
- `feat/noctalia-ui` is pushed for review but not merged; the web configurator remains a follow-up plan.
