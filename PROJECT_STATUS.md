---
status: in-development
progress: 15
version: "0.1.0"
tags: [kde, plasma, kwin, noctalia, arch, cachyos, installer, rice]
scope: "Path-neutral Arch/CachyOS KDE Plasma 6 + Noctalia work/private rice installer with configurable output roles, zones, startup, and autostart."
last_updated: "2026-11-15"
next_steps:
  - Implement output/activity detection and layout presets
  - Add application catalog and installer choices
  - Generate KWin placement, Noctalia, systemd, and runtime artifacts
  - Add startup/autostart, theme engine, installer, tests, and English docs
  - Build Noctalia UI/plugin port and web configurator in follow-up plans
---

# Current State

- Core spec and implementation plan are committed; CLI scaffold and canonical TOML config validation are in place.
- Core backend implementation is in progress on `feat/core`.
- No remote or public push yet; live rice is unchanged until the installer is verified.
