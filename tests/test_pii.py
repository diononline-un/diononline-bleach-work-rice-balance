import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"/home/[A-Za-z0-9._-]+"),
    re.compile(r"(?<!127\.0\.0\.1)\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\."),
    re.compile(r"tailscale", re.IGNORECASE),
    re.compile(r"(?:^|\s)ssh\s", re.IGNORECASE),
    re.compile(r"\bvps\b", re.IGNORECASE),
]
SKIP_PARTS = {".git", ".venv", ".superpowers", ".worktrees"}
SKIP_PREFIXES = ("docs/superpowers", "assets/wallpapers")
# This test itself contains the marker literals on purpose; fixture files build
# their denylist markers by concatenation so they stay scannable.
SKIP_NAMES = {"test_pii.py"}
SCANNED_SUFFIXES = {".md", ".py", ".toml", ".sh", ".js", ".in", ".luau", ".json"}
MANIFEST = ROOT / "assets/wallpapers/manifest.toml"
PROJECT_URL = "https://github.com/diononline-un/diononline-bleach-work-rice-balance"
DOCUMENTATION = {
    "README.md",
    "docs/INSTALL.md",
    "docs/CONFIGURATION.md",
    "docs/ARCHITECTURE.md",
    "docs/PLACEMENT.md",
    "docs/STARTUP.md",
    "docs/THEMING.md",
    "docs/ASSETS.md",
    "docs/TROUBLESHOOTING.md",
    "docs/NOCTALIA.md",
    "docs/SHORTCUTS.md",
}
PLACEHOLDER_MARKERS = ("lorem ipsum", "todo", "tbd", "fixme")


def _skip(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    relative_parts = path.relative_to(ROOT).parts
    return (
        path.name in SKIP_NAMES
        or any(part in SKIP_PARTS for part in relative_parts)
        or any(relative.startswith(prefix) for prefix in SKIP_PREFIXES)
    )


def test_no_personal_data_in_committed_files():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or _skip(path):
            continue
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    assert not hits, "personal data candidates: " + ", ".join(hits)


def test_plugin_and_noctalia_sources_are_scanned():
    plugin_files = sorted((ROOT / "plugins").rglob("*.luau"))
    assert plugin_files, "no plugin sources found"
    for path in plugin_files:
        assert path.suffix in SCANNED_SUFFIXES
        assert not _skip(path), f"plugin source skipped by the scan: {path}"
        assert "plugins" in path.relative_to(ROOT).parts
    for relative in ("defaults/noctalia/config.toml", "defaults/noctalia/media.json"):
        path = ROOT / relative
        assert path.is_file(), f"missing scanned source: {relative}"
        assert not _skip(path), f"Noctalia source skipped by the scan: {relative}"
        if path.suffix in SCANNED_SUFFIXES:
            hits = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if any(pattern.search(line) for pattern in PATTERNS)
            ]
            assert not hits, f"personal data candidates in {relative}: {hits}"


def test_wallpaper_manifest_is_metadata_only():
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["wallpaper"]
    assert entries
    for entry in entries:
        assert set(entry) == {
            "id",
            "file",
            "source",
            "artist",
            "license",
            "sha256",
        }
        assert entry["file"].endswith((".png", ".jpg", ".jpeg", ".webp"))
        assert Path(entry["file"]).name == entry["file"]
        assert entry["source"].startswith("https://")
        assert not any(part in entry["file"] for part in ("/", "\\"))
        assert all(isinstance(value, str) for value in entry.values())


def test_wallpapers_directory_has_no_image_binaries():
    directory = ROOT / "assets/wallpapers"
    files = [path for path in directory.rglob("*") if path.is_file()]
    assert files == [MANIFEST]


def test_manifest_contains_no_personal_data():
    text = MANIFEST.read_text(encoding="utf-8")
    for pattern in PATTERNS:
        assert not pattern.search(text)


def test_documentation_exists_and_has_content():
    for relative in sorted(DOCUMENTATION):
        path = ROOT / relative
        assert path.is_file(), f"missing documentation: {relative}"
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) >= 40, f"thin documentation: {relative}"
        assert "## " in text, f"documentation has no sections: {relative}"
        lowered = text.lower()
        for marker in PLACEHOLDER_MARKERS:
            assert marker not in lowered, f"placeholder {marker!r} in {relative}"


def test_readme_links_every_document():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert PROJECT_URL in readme
    for relative in sorted(DOCUMENTATION):
        if relative == "README.md":
            continue
        assert relative in readme, f"README does not link {relative}"
