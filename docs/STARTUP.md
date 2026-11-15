# Startup And Autostart

Startup and autostart are deliberately separate:

- **Startup** means once at login, regardless of which activity becomes active.
- **Autostart** means the first time an activity becomes active in the current
  login session.

Work applications are not part of the default login set. They start when Work is
first entered, not while Private is active at login.

## Configuration

```toml
[startup]
always = ["gpu-recorder"]
private = ["private-browser", "terminal"]

[autostart.private]
apps = []

[autostart.work]
apps = ["work-browser", "claude"]
```

| Key | Meaning |
| --- | --- |
| `startup.always` | Apps launched at every login. |
| `startup.private` | Apps launched at every login, regardless of the activity Plasma restored. |
| `autostart.<role>.apps` | Apps launched the first time that activity is entered. |

Every id must reference a declared `[[app]]` entry. A role in `autostart` must
also have a matching `[activities.<role>]` section. Invalid references fail
validation before apply writes anything.

## Login Sequence

The generated user units form this chain:

```text
graphical-session.target
        │
        ├── rice-daemon.service      D-Bus service, stays running
        ├── rice-theme-boot.service  one-shot wallpaper selection
        └── rice-startup.service     one-shot startup sets
                 after daemon and boot theme
```

`rice-startup.service` runs `rice startup` once. That command launches
`startup.always` and then `startup.private`, in list order. It writes
`$XDG_RUNTIME_DIR/rice/startup.done` after the launches.

Launching is fire-and-forget. Commands are started in a new session with output
discarded, so a slow application does not block the ones after it. A missing or
empty command in the runtime document fails that startup call with a clear
error; a command that starts and immediately exits is not retried.

The startup marker is written for observability. A manual `rice startup` does
not consult it and launches the sets again. Autostart is the part that
deduplicates automatically.

## Activity Switching

```bash
rice activity private
rice activity work
```

The command:

1. Loads `$XDG_STATE_HOME/rice/runtime.json`.
2. Resolves the KDE activity UUID for the role.
3. Calls `SetCurrentActivity` through `qdbus6`.
4. Runs the autostart set for that role.
5. Writes `$XDG_RUNTIME_DIR/rice/autostart-<role>.done`.

The D-Bus daemon exposes the same operation as `SwitchActivity`, which lets KWin
shortcuts and the future shell trigger it without starting a new process.

An autostart set runs only when its marker is absent. Entering Work, leaving,
and entering Work again in the same login therefore does not launch duplicate
windows. A new login starts with an empty runtime directory and the sets are
eligible again.

Activity roles are validated before use. The role must be a plain name without
path separators because it becomes part of the marker file name.

## Markers

| Marker | Written by | Meaning |
| --- | --- | --- |
| `$XDG_RUNTIME_DIR/rice/startup.done` | `rice startup` | Login startup sets were launched. |
| `$XDG_RUNTIME_DIR/rice/autostart-private.done` | `rice activity private` | Private autostart ran this session. |
| `$XDG_RUNTIME_DIR/rice/autostart-work.done` | `rice activity work` | Work autostart ran this session. |

`XDG_RUNTIME_DIR` must be set. Without it the startup module refuses to guess a
location, because a wrong location could leak markers across sessions.

Markers vanish when the session ends. If an application crashes and you want to
retry its autostart set without logging out, remove the matching marker and call
`rice activity <role>` again:

```bash
rm "$XDG_RUNTIME_DIR/rice/autostart-work.done"
rice activity work
```

## Work And Private Semantics

The zones do not change when the activity changes. Only the set of matching
placement rules and the autostart set change.

A typical configuration:

- Private starts the private browser, Steam, YouTube Music, and the terminal at
  login.
- Work starts nothing at login.
- Entering Work starts the work browser and Work-side tools once.
- Entering Private after Work starts the private set only if it was not already
  launched at login.

The installer builds this shape from the selected app catalog. It does not add
Work applications to the login set unless the catalog marks them as private as
well.

## Initial Activity

The current core does not force a specific activity at login. Plasma restores
the activity from the previous session. `startup.private` remains a declaration
of which set belongs to login; the service launches that set regardless of the
activity Plasma restored.

Explicit initial-activity selection is planned alongside the configurator. Until
then, configure Plasma's own session restoration if the login activity matters.

## Inspecting Startup

```bash
systemctl --user status rice-daemon.service
systemctl --user status rice-startup.service
systemctl --user status rice-theme-boot.service
journalctl --user -u rice-startup.service -b
```

Run the commands manually to test configuration changes without logging out:

```bash
rice startup
rice activity work
```

Remember that manual startup runs are not deduplicated. Use the marker removal
described above when retrying autostart.

## Limitations

- Application launch order is list order; the runtime does not wait for one app
  to be ready before starting the next.
- There is no retry when an application exits during launch.
- The startup set is not skipped when the matching activity is not current; it
  is a login set by definition.
- Initial activity selection is future work.
- The Noctalia UI tabs for editing these sets are future work. Edit `rice.toml`
  and run `rice apply` in the current core.
