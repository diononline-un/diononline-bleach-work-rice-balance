# Shortcuts

rice registers its keybindings from the generated KWin script. The bindings are
part of `$XDG_DATA_HOME/kwin/scripts/rice-placement/contents/code/main.js`, which
`rice apply` writes from `templates/kwin/main.js.in`. No shortcut is stored in a
hand-maintained KDE file, and no connector name is hard coded in the script.

## Binding Table

| Shortcut | Action | Implementation |
| --- | --- | --- |
| `Meta+M` | Maximize or restore the active window | KWin script |
| `Meta+N` | Minimize the active window | KWin script |
| `Meta+Q` | Close the active window | KWin script |
| `Meta+H` | Tile the active window to the left half | KWin script |
| `Meta+J` | Tile the active window to the right half | KWin script |
| `Meta+Left` | Focus the previous window on this display | KWin script |
| `Meta+Right` | Focus the next window on this display | KWin script |
| `Meta+1` | Move the active window to role `main` | KWin script |
| `Meta+2` | Move the active window to role `side` | KWin script |
| `Meta+3` | Move the active window to role `portrait` | KWin script |
| `Meta+Return` | Open a terminal | `rice` daemon |
| `Meta+Shift+Return` | Open an animated terminal | `rice` daemon |
| `Ctrl+Alt+H` | Toggle the shortcut cheatsheet panel | `rice` daemon |
| `Ctrl+Alt+Shift+Right` | Apply the next wallpaper | `rice` daemon |
| `Ctrl+Alt+Shift+Left` | Apply the previous wallpaper | `rice` daemon |
| `Ctrl+Alt+1` | Switch to the Work activity | `rice` daemon |
| `Ctrl+Alt+2` | Switch to the Private activity | `rice` daemon |
| `Ctrl+Alt+Shift+1` | Quickstart the Work set | `rice` daemon |
| `Ctrl+Alt+Shift+2` | Quickstart the Private set | `rice` daemon |
| `Ctrl+Alt+Shift+Space` | Quickstart the current activity | `rice` daemon |
| `Ctrl+Alt+R` | Reapply the default window layout | `rice` daemon |

Daemon-backed entries call `org.rice.Rice` on `/Rice`. When the daemon is not
running the shortcut does nothing visible; start it with
`systemctl --user start rice-daemon.service`.

## Output Roles

Move shortcuts target a role, not a connector. `OUTPUT_ROLES` in the generated
script maps each configured role to its connector, and `connectorForRole`
resolves the target at runtime.

| Role | Meaning | Assigned by the installer |
| --- | --- | --- |
| `main` | Primary display | The output reported as primary by KScreen, wherever it appears in the list. |
| `side` | First non-primary display | First secondary output in KScreen order. |
| `portrait` | Second non-primary display | Second secondary output in KScreen order. |

A single-output install has no `side` or `portrait` connector. `Meta+2` and
`Meta+3` then do nothing, which is intentional; the script never guesses a
display. A fourth output keeps its own id and geometry with the fallback role
`extra`, which has no move shortcut.

The installer derives the roles from output identity, so a primary display at
index 1 of the KScreen list still becomes `main`, while the two non-primary
outputs become `side` and `portrait` in list order. Id and geometry are kept
unchanged. See [Placement](PLACEMENT.md) for the zone model.

## Conflict Cleanup

KDE ships default bindings that collide with rice: window quick tile left and
right, the activity manager shortcut, and the first three task manager entries.
`rice apply` generates `rice-shortcuts.service`, and the apply reload sequence
enables it together with the daemon and startup units.

The service runs:

```bash
rice shortcuts disable-conflicts
```

That command talks to `org.kde.kglobalaccel` on the session bus and clears the
listed actions. KGlobalAccel publishes components asynchronously after login,
so the command retries until a full pass has seen every wanted action or the
retry budget is exhausted. Each cleared action is printed as
`component:action`.

Run it manually after a KDE update adds a new default:

```bash
systemctl --user status rice-shortcuts.service
rice shortcuts disable-conflicts
```

If nothing collides, the command reports that no conflicting shortcuts were
found and exits successfully.

## Changing Bindings

Edit the `registerShortcut` calls in `templates/kwin/main.js.in`, then run
`rice apply` and reload KWin. KDE's System Settings can also rebind a
registered shortcut, but a later apply may register the default again, so keep
the template and the desktop settings aligned.

KWin only loads the script when `rice-placementEnabled` is set. `rice apply`
writes that key and asks KWin to reconfigure; a manual check is:

```bash
kwriteconfig6 --file kwinrc --group Plugins --key rice-placementEnabled true
qdbus6 org.kde.KWin /KWin reconfigure
```

## Quickstart Semantics

The quickstart shortcuts launch the set that belongs to an activity:

- Private uses the login startup set (`startup.private`), so a fresh Private
  session receives the same applications as a login.
- Work uses the Work autostart set (`autostart.work.apps`), which is the set
  intended for entering the Work activity.
- Quickstart current inspects the active activity and picks the matching set.

Applications already running are not started twice. The runtime markers under
`$XDG_RUNTIME_DIR/rice/` suppress duplicate autostart runs for the login
session. See [Startup](STARTUP.md) for the full distinction.

## Arrange

`Ctrl+Alt+R` and `rice arrange` ask the daemon to load the generated one-shot
`arrange.js` through KWin's scripting D-Bus API. The script walks the current
window list and re-applies every matching rule for the active activity. It is a
one-shot helper: the persistent placement logic lives in the main script.

This shortcut requires a running rice daemon and a KWin session that accepts
scripting D-Bus calls. On a nested session or a compositor other than KWin the
call fails with a single error line instead of moving windows.

## Cheatsheet

`Ctrl+Alt+H` opens `rice/cheatsheet:panel`. The panel is read-only and groups
the bindings by window, workspace, theme, and activity. Displays are labelled
`Main`, `Side`, and `Portrait` to match the role model, so a screenshot from one
machine does not show another machine's connector names.

The panel source lives in `plugins/cheatsheet/panel.luau`. Keep it in sync with
the template when adding a binding; the plugin does not parse the KWin script.

## Current Limitations

- `registerShortcut` uses the KWin scripting API. Bindings are visible only
  while the rice KWin script is enabled.
- A role without a resolved connector silently skips the move. This is safer
  than a fallback that moves a window to an unrelated display.
- The daemon must be running for terminal, theme, activity, cheatsheet, and
  arrange shortcuts. Plain window management still works without it.
- Live verification of these bindings against the target KDE Plasma 6 release
  is still pending.
- Rebinding through System Settings is supported by KDE but is not reflected
  back into `rice.toml`; the TOML file stays the source for generated bindings.
