# Placement

Placement controls three things: which display receives a window, which
rectangle inside that display the window occupies, and which activity the rule
belongs to. The same zones serve both Work and Private; switching activities
changes which application occupies a zone, not the geometry itself.

## Outputs

The installer reads `kscreen-doctor -j` and keeps only outputs that are both
connected and enabled. Each output becomes a record with:

- an internal `id` (`main` for the primary output, `output-N` otherwise),
- the real `connector` name used by KWin and Noctalia,
- `x`, `y`, `width`, and `height` in the global virtual desktop,
- a `primary` flag.

The installer writes the primary output as role `main`, the first non-primary
output as `side`, and the second non-primary output as `portrait`, regardless of
the order KScreen returns. Further outputs keep the fallback role `extra`.
Roles drive the move shortcuts; zones bind to output ids, and generated
placement rules bind to connector names.

If a configured connector is absent at runtime, the KWin script cannot resolve
the output. It skips the placement for that rule and leaves the application
running. No fallback output is guessed.

## Zones

A zone is a rectangle relative to the usable client area of one output. The
usable area excludes exclusive shell reserves such as a top bar, so a zone never
sits underneath the panel.

```toml
[[zone]]
id = "center-left"
output = "main"
kind = "app"
x = 0.0
y = 0.0
w = 0.5
h = 1.0
gap_px = 8
```

Coordinates are fractions from 0 to 1, measured from the top-left of the usable
area. `x + w` and `y + h` may not exceed 1. Width and height must be positive.
`gap_px` is an inward inset: the final rectangle is shifted by the gap and
shrunk by twice the gap, with a minimum window size enforced by the script.

Two zone kinds exist:

- `app` zones are legal placement targets for application rules.
- `shell` zones are anchors for desktop widgets such as clocks or media panels.
  They do not receive application windows.

Overlaps between app zones are allowed. The higher-priority placement rule wins;
on equal priority the later rule in the configuration wins. This makes it
possible to define a broad fallback zone and a smaller exception zone.

## Presets

`rice.layouts.choose_layout` selects a preset during installation:

| Detected setup | Preset |
| --- | --- |
| One output at least 3440 pixels wide | `ultrawide` |
| Three or more outputs | `triple` |
| Anything else | `single-split` |

Preset definitions also exist as documentation and defaults under
`defaults/layouts/`. The Python layout builder is authoritative at install time.

### Single Split

One display with two equal center tiles:

| Zone | x | w | Purpose |
| --- | --- | --- | --- |
| `center-left` | 0.00 | 0.50 | Main work/private tile. |
| `center-right` | 0.50 | 0.50 | Secondary tile. |

### Triple

Three displays: a primary split in half, a side display split in half, and a
portrait display used as one full-height area.

| Zone | Output | x | w |
| --- | --- | --- | --- |
| `main-left` | primary | 0.00 | 0.50 |
| `main-right` | primary | 0.50 | 0.50 |
| `side-left` | second | 0.00 | 0.50 |
| `side-right` | second | 0.50 | 0.50 |
| `portrait-full` | third | 0.00 | 1.00 |

Selection is by output order after filtering disabled outputs. The preset names
the second and third outputs `side` and `portrait` conceptually; the generated
zone records reference their real internal output ids.

### Ultrawide

One wide display with two shell edges and two center app columns:

| Zone | Kind | x | w | Purpose |
| --- | --- | --- | --- | --- |
| `edge-left` | shell | 0.00 | 0.20 | Left widget rail. |
| `center-left` | app | 0.22 | 0.28 | Main work/private tile. |
| `center-right` | app | 0.50 | 0.28 | Secondary tile. |
| `edge-right` | shell | 0.80 | 0.20 | Right widget rail. |

The outer rails hold clock, calendar, media, or status widgets so they stay
visible while the center columns are occupied. The top bar remains a full-width
element and is not part of a zone.

## Default Placements

The installer derives placements from the chosen preset and the selected app
catalog. The logical roles below map to concrete zones per preset.

| App | Logical zone | Mode |
| --- | --- | --- |
| `private-browser` | private | normal |
| `work-browser` | work | normal |
| `steam` | private | normal |
| `youtube-music` | private side | normal |
| `claude` | private side; work side on Work | normal |
| `opencode` | private side; work side on Work | normal |
| `terminal` | private side; work side on Work | normal |
| `gpu-recorder` | private side; work side on Work | normal |
| `discord` | portrait | fullscreen |

Logical-to-concrete zone mapping:

| Preset | private | private side | work side | portrait |
| --- | --- | --- | --- | --- |
| `single-split` | `center-left` | `center-left` | `center-right` | `center-right` |
| `ultrawide` | `center-left` | `center-left` | `center-right` | `center-right` |
| `triple` | `main-left` | `side-left` | `side-right` | `portrait-full` |

Work applications listed with both activities receive a rule for each activity.
The same app can therefore occupy the private side tile in Private and the work
side tile in Work.

## KWin Matching

The generated rule for a placement contains:

- the lowercased `wm_class` from the app entry,
- the optional lowercased `match_title`,
- the resolved activity id,
- the output connector,
- relative zone geometry and gap,
- the placement mode.

Matching order is window class first, then title substring. A rule with neither
a window class nor a title never matches. Activity must be current unless the
rule activity id is empty. The mode is applied after placement:

- `normal` leaves the window floating in the zone rectangle,
- `maximized` maximizes it on the target output,
- `fullscreen` sets fullscreen on the target output.

The script remembers the window and the activity in which it was placed. A
window that is already placed in the current activity is not moved again, which
prevents a focus change from fighting manual user movement.

## Desktop Widget Anchors

`[[desktop_widget]]` entries reference a shell zone. The generator computes the
absolute pixel center of that zone:

```text
cx = output.x + output.width  * (zone.x + zone.w / 2)
cy = output.y + output.height * (zone.y + zone.h / 2)
```

Those coordinates and the widget scale are written into the generated Noctalia
include under `rice_` keys. Because the math uses output geometry, a manually
written configuration should include real `x`, `y`, `width`, and `height` values
for every output. The bare canonical template has no geometry and is a
diagnostic default, not a complete desktop layout.

## Custom Layouts

A custom layout is a normal configuration edit:

1. Declare one `[[output]]` per connected display with real connector names.
2. Declare zones with ids that describe their purpose.
3. Keep every zone inside the 0-to-1 bounds and give it a positive size.
4. Declare placements from app ids to zone ids for the intended activity.
5. Run `rice apply --dry-run` to validate the references.
6. Run `rice apply` to write the KWin script and reload it.

Use `priority` to resolve overlapping zones intentionally. Use separate zone ids
for Work and Private only when the geometry genuinely differs; otherwise keep
one zone set and vary the placement activity.

A visual canvas for dragging and resizing zones is future work. The current core
expects TOML edits.

## Verifying Placement

```bash
rice doctor
rice apply --dry-run
rice apply
```

`rice doctor` reports missing Noctalia or D-Bus tooling, undetected outputs, and
configuration errors. After apply, the KWin script is enabled through
`kwinrc` and KWin is asked to reconfigure. If windows do not move, the usual
causes are a window class mismatch, a rule for a different activity, or a
connector name that no longer exists. See [Troubleshooting](TROUBLESHOOTING.md).
