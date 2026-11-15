# Configurator

`rice config` starts a local web editor for `rice.toml`. The editor reads the
saved document, lets you change it in structured forms, validates the result,
and writes it back through the same configuration and apply pipeline the CLI
uses. There is no second source of truth: the file on disk stays canonical.

## Start The Server

```bash
rice config
rice-config
rice config --no-browser
```

All three entry points run the same server. `rice config` prints the URL and
opens your default browser. `--no-browser` skips the browser launch so you can
open the printed URL yourself. `rice-config` is the standalone launcher for the
same module; it accepts the same flag. The installed launchers read the runtime
tree from `$XDG_DATA_HOME/rice`, so they work from any directory.

The server binds to `127.0.0.1` on a random free port for the lifetime of the
command. Stop it with Ctrl-C. It never runs in the background and does not
install a systemd unit.

## Security Model

The server protects configuration data in three ways.

- **Loopback only.** The socket binds to `127.0.0.1`, not `0.0.0.0`. Other
  machines on your network cannot reach it, and there is no option to expose
  it.
- **Per-session bearer token.** `run_server` generates a random token with
  `secrets.token_urlsafe(32)` for every start. The URL carries it as
  `?token=...`. The page stores the token in `sessionStorage`, strips it from
  the address bar, and sends `Authorization: Bearer <token>` on each API call.
  Tokens never reach the config file, logs, or disk.
- **Constant-time comparison.** The server checks the header with
  `hmac.compare_digest`, so a failed attempt does not leak token bytes through
  timing.

Unauthenticated requests to `/api/state`, `/api/outputs`, `/api/config`,
`/api/validate`, `/api/apply`, `/api/backup`, and `/api/restore` return
`401 unauthorized`. Only `/api/health` and the three static files are public.

The UI loads no external resources. `index.html`, `style.css`, and `app.js` are
served from a fixed allowlist under `src/web`, so a crafted path cannot escape
the asset directory. There is no analytics, no remote font, and no CDN.

The configurator never executes commands from the document. Apply runs the
existing `apply_config` path, which writes generated files and reloads KWin,
Noctalia, and the user units. Application commands stay argv arrays.

## Tabs

The left navigation groups the document by section.

- **Apps** edits the app catalog entries: id, display name, argv, KWin window
  class, and the activities the app belongs to. Removing an app also drops its
  placement, startup, and autostart references.
- **Outputs** sets connector roles (`main`, `side`, `portrait`, `custom`), a
  custom role name, and the primary flag. Connectors come from the saved
  document and the live `kscreen-doctor` probe, never a fixed list.
- **Layout** edits zones on a canvas per output.
- **Placement** maps an app to a zone, with mode, activity, and priority.
- **Startup** edits the login startup sets per activity.
- **Autostart** edits the first-entry app sets per activity.
- **Widgets** edits the desktop widget anchors that apply renders into the
  Noctalia config.
- **Theme** edits the wallpaper directory, output list, rotation intent, and
  the fullscreen and idle guards.
- **Apply** shows validation results, run status, and the last error.

Every edit changes the in-memory document only and marks it dirty. A
`beforeunload` prompt warns before you leave with unsaved changes.

## Canvas And Zones

The Layout tab draws one canvas per configured output, using the detected
width and height when available and a 16:9 box otherwise. Drag a zone to move
it and drag the corner handle to resize it.

Zone geometry is relative: `x`, `y`, `w`, and `h` stay inside `[0, 1]` and snap
to `0.01`. The editor enforces a `0.05` minimum size and keeps `x + w` and
`y + h` inside the canvas, which mirrors the geometry rules in
`rice.config.validate`. Adding a zone creates a unique `custom-<n>` app zone on
the selected output. Removing one confirms first and drops dependent placement
rows so the document stays valid.

## Validate, Save, And Apply

The footer buttons map to the API.

| Button | Request | Effect |
| --- | --- | --- |
| Validate | `POST /api/validate` | Runs `validate_config` on the saved document and lists errors. |
| Save | `PUT /api/config` | Validates the posted document, then writes it atomically with `save_config`. |
| Apply | `PUT /api/config`, then `POST /api/apply` | Saves first, then runs `apply_config` against the saved file. |

Save returns HTTP 400 with an `errors` array when the document breaks a
reference or a geometry rule, and the UI shows each message in the Apply tab
and status bar. Apply refuses to run on an invalid document and reports a
failed run as a single error line.

Apply is the only action with side effects beyond `rice.toml`. It rewrites the
KWin script, the merged Noctalia config, the user units, and the runtime JSON,
and then reloads the session. Use Validate first when you are unsure.

## Backup And Restore

`POST /api/backup` copies the current `rice.toml` to
`$XDG_STATE_HOME/rice/web-backups/<YYYYMMDD-HHMMSS>/rice.toml` and returns the
path. Repeated calls in the same second get a numeric suffix.

`POST /api/restore` takes `{"path": "..."}`, loads that file, validates it, and
writes it over `rice.toml`. The server rejects any path outside the web-backup
root, so restore cannot read arbitrary files. Apply does not run automatically
after a restore; review the document, then press Apply or run `rice apply`.

These backups are separate from the apply backups in
`$XDG_STATE_HOME/rice/backups`. Uninstall keeps both directories.

## HTTP API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/health` | no | Liveness probe, returns `{"status": "ok"}`. |
| GET | `/api/state` | yes | Config, validation errors, detected outputs, and app catalog. |
| GET | `/api/outputs` | yes | Detected outputs only. |
| PUT | `/api/config` | yes | Validate and save `{"config": {...}}`. |
| POST | `/api/validate` | yes | Validate the saved document. |
| POST | `/api/apply` | yes | Run `apply_config` on the saved document. |
| POST | `/api/backup` | yes | Copy `rice.toml` into the web-backup root. |
| POST | `/api/restore` | yes | Restore a file from the web-backup root. |

Output detection shells out to `kscreen-doctor`. If that probe fails, the
endpoint returns an empty list instead of an error, so the editor still loads.

## Limitations

- The editor has no browser automation test yet. Unit tests cover the API,
  static serving, token handling, and asset structure, but pointer dragging and
  layout rendering still need a manual check in a real browser.
- Apply runs the real runtime: it writes generated files and asks KWin,
  Noctalia, and systemd to reload. There is no preview mode inside the
  configurator.
- The document is a single user's `rice.toml`. There is no multi-user or remote
  editing support, and no concurrent-write detection beyond the atomic save.
- Restore only accepts paths inside the web-backup root. Copy a file there
  first if you want to restore an older apply backup.
- Zone editing works on relative geometry only. Pixel-level control stays in
  `rice.toml`.
