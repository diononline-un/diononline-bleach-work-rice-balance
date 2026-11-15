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
# This test itself and the public-safety denylist fixture contain the marker
# literals on purpose.
SKIP_NAMES = {"test_pii.py", "test_apps.py"}
SCANNED_SUFFIXES = {".md", ".py", ".toml", ".sh", ".js", ".in"}
MANIFEST = ROOT / "assets/wallpapers/manifest.toml"


def _skip(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return (
        path.name in SKIP_NAMES
        or any(part in SKIP_PARTS for part in path.parts)
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
