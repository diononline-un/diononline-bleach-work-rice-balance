# Appearance and Window Opacity

`rice appearance` installs conservative KWin rules for whole-window opacity.
KWin cannot detect which parts of an application are empty: an app must draw a
transparent background itself for the wallpaper to show through only in empty
areas. The generated rules therefore make the whole window translucent, while
games stay fully opaque; fullscreen windows are never forced by rice.

## Apply

```bash
rice appearance apply
rice appearance status
rice appearance remove
```

`apply` backs up `kwinrulesrc` under
`$XDG_STATE_HOME/rice/backups/<timestamp>/`, writes only rice-owned rule groups,
and reloads KWin. `remove` removes only groups prefixed with
`rice-appearance-`; existing user rules are preserved.

## Default profile

| Applications | Active opacity | Inactive opacity |
| --- | ---: | ---: |
| VS Code, OpenCode | 92% | 86% |
| Claude, Claude Desktop, Slack, Discord | 94% | 88% |
| Dolphin | 96% | 92% |
| Obsidian, Thunderbird | 94% | 88% |

The browser classes (`brave-browser`, `google-chrome`, `chromium`, `firefox`)
are handled by a small KWin script instead of a rule. Normal browser windows use
92%/86%, while fullscreen browser windows are forced to 100% opacity so video
stays solid. Inline video inside a normal browser window still inherits the
window opacity; KWin cannot isolate a web page's video surface.

`steam`, `steam_app_*`, and `gamescope` are forced to 100%. VLC, mpv, Celluloid,
Haruna, SMPlayer, and YouTube Music are explicitly kept at 100%. The profile
never forces fullscreen; windows that are not listed keep the user's current KWin
appearance.

Terminal transparency is better handled natively by Alacritty, Kitty, or
Konsole. Combining native terminal opacity with these KWin rules would stack
the two effects.

## Limitations

- The rules make the whole window translucent, including text. Keep values
  above 85–90% for text-heavy apps.
- Chromium browsers and Electron apps generally do not provide selective
  background alpha; the KWin rule is the practical option.
- Transparent windows look best with a working KWin blur effect. Without blur,
  busy wallpapers can reduce readability.
- Games, Steam, VLC, mpv, Celluloid, Haruna, SMPlayer, and YouTube Music are deliberately kept opaque.
- Fullscreen browser video is kept opaque by the browser guard; inline video cannot be isolated from the page.
- Editing the rules through System Settings may replace the generated groups;
  rerun `rice appearance apply` to restore the rice profile.
