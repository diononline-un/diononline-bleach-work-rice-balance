# Assets And Attribution

The repository is metadata-only for visual assets. It contains no wallpaper
binaries, no screenshots of third-party artwork, and no redistributed image
packs. The theme engine works with files that you supply locally.

## Why Metadata Only

Wallpapers are frequently licensed for personal use, sold, or shared under terms
that do not permit redistribution in a public repository. Committing the files
would make the project a redistribution point for material it does not own. The
core therefore separates two things:

- **The repository** stores identifiers, attribution links, artist names, usage
  terms, and optional hashes.
- **Your machine** stores the actual image files in the directory configured as
  `theme.wallpaper_dir`.

The privacy test suite enforces the separation. It fails if any image file
appears under `assets/wallpapers/`, and it requires that the only file in that
directory is the manifest.

## Manifest Format

`assets/wallpapers/manifest.toml` is a TOML document with one or more entries:

```toml
[[wallpaper]]
id = "example"
file = "example.png"
source = "https://example.invalid/source"
artist = "Example Artist"
license = "private-personal-use-only"
sha256 = ""
```

| Key | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable identifier used by tooling and documentation. |
| `file` | yes | Base file name inside the user's wallpaper directory. It must not contain a path separator. |
| `source` | yes | Public attribution link for the original artwork. Must use HTTPS. |
| `artist` | yes | Credited artist or author. |
| `license` | yes | Usage terms for the local copy, for example personal-use only. |
| `sha256` | yes | Optional integrity hash. An empty string means unset. |

The shipped entry is a placeholder. Replace it with entries for your own files,
or keep your metadata in a local note and leave the placeholder untouched. Do
not commit the images themselves.

All values are strings. The test suite validates the key set, the image
extension, the base-name rule, the HTTPS source, and the absence of personal
network data in the manifest.

## Attribution Is Not A License

An artist name and a source link are credit, not permission. The `license` field
records what you believe your local copy permits. It does not grant anyone else
the right to redistribute the file. If a source says personal use only, the
image stays on your machine and out of the repository.

When in doubt, use one of these instead:

- an image you created,
- a public-domain work,
- a CC0 work that explicitly allows redistribution,
- a purchased license that allows your intended use.

## Adding Local Wallpapers

1. Create the wallpaper directory, for example the path configured in
   `theme.wallpaper_dir`.
2. Copy supported files into it: `.png`, `.jpg`, `.jpeg`, or `.webp`.
3. Keep file names stable if you add manifest entries, because `file` is matched
   by base name.
4. Optionally compute a hash:

```bash
sha256sum "$HOME/Pictures/rice-wallpapers/example.png"
```

5. Put the hash in the `sha256` field if you want an integrity check later.
6. Run `rice theme next` to verify the engine sees the files.

The engine sorts by file name and ignores unsupported extensions. It does not
recursively scan subdirectories.

## Screenshots And Showcase Material

Screenshots of the desktop can reveal application content, account names, and
window titles. Only publish screenshots that you created, that show no private
data, and whose visible artwork you have the right to share. Future showcase
material should use own, public-domain, or CC0 assets and carry explicit
attribution. The current core does not ship a showcase directory or screenshots.

## What The Tests Enforce

- No personal host names, remote endpoint names, private network names,
  credentials, IP addresses, or absolute user home paths in committed files.
- No image binary anywhere under `assets/wallpapers/`.
- Manifest entries have exactly the documented keys and sensible values.
- Manifest source links are HTTPS and contain no personal network data.

These checks run with the normal test suite. A future asset addition that
violates the policy fails the suite before it can be merged.

## Removal

Removing a manifest entry does not touch your files. Removing a local wallpaper
is a normal file delete in your own directory. Uninstalling the rice leaves
wallpapers and metadata in place.
