# Appearance and Window Opacity

Application windows are fully opaque. `rice appearance` removes legacy KWin
opacity rules owned by rice and does not add new ones. It does not touch the
Noctalia shell: bars, capsules, panels, and desktop widgets keep their separate
glass styling.

## Apply

```bash
rice appearance apply
rice appearance status
rice appearance remove
```

`apply` backs up `kwinrulesrc` under
`$XDG_STATE_HOME/rice/backups/<timestamp>/`, removes only groups prefixed with
`rice-appearance-`, and reloads KWin. Existing user-defined rules are preserved.
`remove` performs the same cleanup.

## Policy

- Application windows: 100% opaque.
- Noctalia shell, bar, capsules, panels, desktop widgets: controlled by the
  Noctalia configuration, not by this command.
- Browsers, editors, media players, Steam, and games: all application windows
  follow the solid-window policy.
- Any previous rice opacity profile is removed by `rice appearance apply`.

## Limitations

- This command only changes KWin window rules; it cannot make an application
  draw transparent surfaces without rules.
- Noctalia glass effects are separate and remain enabled.
- Running the profile again is safe and keeps user-defined rules.
