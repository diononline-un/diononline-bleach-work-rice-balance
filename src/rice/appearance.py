"""KWin appearance profile: controlled whole-window transparency.

KWin cannot selectively make only an app's empty surfaces transparent. This
module applies conservative active/inactive opacity rules for normal windows
and keeps fullscreen apps and games fully opaque.
"""

from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import config_home, data_home, state_home

RULE_PREFIX = "rice-appearance-"
RULE_ORDER = "General"
RULE_APPS = (
    ("code", "VS Code", "code", 92, 86),
    ("claude", "Claude", "claude", 94, 88),
    ("claude-desktop", "Claude Desktop", "com.anthropic.Claude", 94, 88),
    ("opencode", "OpenCode", "ai.opencode.desktop", 92, 86),
    ("slack", "Slack", "slack", 94, 88),
    ("discord", "Discord", "discord", 94, 88),
    ("dolphin", "Dolphin", "dolphin", 96, 92),
    ("obsidian", "Obsidian", "obsidian", 94, 88),
    ("thunderbird", "Thunderbird", "thunderbird", 94, 88),
)
EXCEPTION_GAMES = "games"
EXCEPTION_MEDIA = "media"
BROWSER_SCRIPT_NAME = "rice-browser-opacity"
BROWSER_SCRIPT = r"""// Rice: browsers stay readable while fullscreen video stays opaque.
const BROWSERS = ["brave-browser", "google-chrome", "chromium", "firefox"];
const ACTIVE = 0.92;
const INACTIVE = 0.86;

function sync(win) {
    if (!win || !win.normalWindow) return;
    const cls = (win.resourceClass || "").toLowerCase();
    if (BROWSERS.indexOf(cls) < 0) return;
    win.opacity = win.fullScreen ? 1.0 : (win.active ? ACTIVE : INACTIVE);
}

function watch(win) {
    if (!win) return;
    sync(win);
    win.fullScreenChanged.connect(function () { sync(win); });
    win.activeChanged.connect(function () { sync(win); });
}

workspace.windowAdded.connect(watch);
workspace.windowActivated.connect(function (win) { sync(win); });
const existing = workspace.windowList();
for (let i = 0; i < existing.length; i++) watch(existing[i]);
"""


@dataclass(frozen=True)
class AppearanceResult:
    path: Path
    groups: tuple[str, ...]
    backup: Path | None = None


def _parser() -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    return parser


def _rules_path(path: Path | None = None) -> Path:
    return Path(path) if path is not None else config_home() / "kwinrulesrc"


def _read(path: Path) -> configparser.RawConfigParser:
    parser = _parser()
    if path.is_file():
        parser.read(path, encoding="utf-8")
    if not parser.has_section(RULE_ORDER):
        parser.add_section(RULE_ORDER)
    return parser


def _set(parser: configparser.RawConfigParser, group: str, values: dict) -> None:
    if not parser.has_section(group):
        parser.add_section(group)
    for key, value in values.items():
        parser.set(group, key, str(value))


def _base_values(description: str, active: int, inactive: int) -> dict:
    return {
        "Description": description,
        "opacityactive": active,
        "opacityactiverule": 2,
        "opacityinactive": inactive,
        "opacityinactiverule": 2,
        "types": 1,
    }


def _rule_groups() -> list[tuple[str, dict]]:
    groups: list[tuple[str, dict]] = [
        (
            RULE_PREFIX + EXCEPTION_GAMES,
            {
                **_base_values("Rice appearance: game exception", 100, 100),
                "wmclass": "steam|steam_app_.*|gamescope",
                "wmclassmatch": 3,
                "wmclasscomplete": "false",
            },
        ),
        (
            RULE_PREFIX + EXCEPTION_MEDIA,
            {
                **_base_values("Rice appearance: media exception", 100, 100),
                "wmclass": "vlc|mpv|celluloid|haruna|smplayer|com.github.th-ch.youtube-music",
                "wmclassmatch": 3,
                "wmclasscomplete": "false",
            },
        ),
    ]
    for slug, label, wmclass, active, inactive in RULE_APPS:
        groups.append(
            (
                RULE_PREFIX + slug,
                {
                    **_base_values(f"Rice appearance: {label}", active, inactive),
                    "wmclass": wmclass,
                    "wmclassmatch": 1,
                    "wmclasscomplete": "false",
                },
            )
        )
    return groups


def _remove_managed(parser: configparser.RawConfigParser) -> list[str]:
    removed = []
    for group in list(parser.sections()):
        if group.startswith(RULE_PREFIX):
            parser.remove_section(group)
            removed.append(group)
    order = [
        item
        for item in parser.get(RULE_ORDER, "Order", fallback="").split(",")
        if item and not item.startswith(RULE_PREFIX)
    ]
    parser.set(RULE_ORDER, "Order", ",".join(order))
    return removed


def _backup(path: Path) -> Path | None:
    if not path.is_file():
        return None
    root = state_home() / "rice" / "backups"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = root / stamp
    suffix = 0
    while target.exists():
        suffix += 1
        target = root / f"{stamp}-{suffix}"
    target.mkdir(parents=True)
    destination = target / path.name
    shutil.copy2(path, destination)
    return destination


def _write(path: Path, parser: configparser.RawConfigParser) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".kwinrules-", suffix=".rc", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            parser.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _browser_script_root() -> Path:
    return data_home() / "kwin" / "scripts" / BROWSER_SCRIPT_NAME


def install_browser_script(runner=None, data_dir: Path | None = None) -> Path:
    """Install and enable the browser fullscreen-opacity guard."""
    root = (Path(data_dir) if data_dir is not None else data_home()) / "kwin" / "scripts" / BROWSER_SCRIPT_NAME
    code = root / "contents" / "code" / "main.js"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text(BROWSER_SCRIPT, encoding="utf-8")
    (root / "metadata.json").write_text(
        '{\n  "KPackageStructure": "KWin/Script",\n  "KPlugin": {\n    "Id": "rice-browser-opacity",\n    "Name": "Rice Browser Opacity",\n    "Description": "Keep fullscreen browser video opaque",\n    "Version": "1.0",\n    "License": "MIT"\n  },\n  "X-Plasma-API": "javascript"\n}\n',
        encoding="utf-8",
    )
    run = runner or subprocess.run
    run([
        "kwriteconfig6", "--file", "kwinrc", "--group", "Plugins",
        "--key", f"{BROWSER_SCRIPT_NAME}Enabled", "true",
    ], check=False)
    run([
        "qdbus6", "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript",
        str(code), f"{BROWSER_SCRIPT_NAME}-live",
    ], check=False)
    run(["qdbus6", "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start"], check=False)
    return root


def remove_browser_script(runner=None) -> None:
    run = runner or subprocess.run
    root = _browser_script_root()
    if root.exists():
        shutil.rmtree(root)
    run([
        "kwriteconfig6", "--file", "kwinrc", "--group", "Plugins",
        "--key", f"{BROWSER_SCRIPT_NAME}Enabled", "false",
    ], check=False)


def apply_rules(
    path: Path | None = None,
    *,
    dry_run: bool = False,
    runner=None,
) -> AppearanceResult:
    """Install the rice opacity rules and reload KWin."""
    path = _rules_path(path)
    parser = _read(path)
    _remove_managed(parser)
    groups = []
    for group, values in _rule_groups():
        _set(parser, group, values)
        groups.append(group)
    existing_order = parser.get(RULE_ORDER, "Order", fallback="")
    parser.set(
        RULE_ORDER,
        "Order",
        ",".join([*(group for group, _ in _rule_groups()), existing_order]).strip(","),
    )
    if dry_run:
        return AppearanceResult(path, tuple(groups))
    backup = _backup(path)
    _write(path, parser)
    install_browser_script(runner)
    (runner or subprocess.run)(
        ["qdbus6", "org.kde.KWin", "/KWin", "reconfigure"],
        check=False,
    )
    return AppearanceResult(path, tuple(groups), backup)


def remove_rules(
    path: Path | None = None, *, dry_run: bool = False, runner=None
) -> AppearanceResult:
    """Remove only the rules owned by rice."""
    path = _rules_path(path)
    if not path.is_file():
        return AppearanceResult(path, ())
    parser = _read(path)
    removed = _remove_managed(parser)
    if dry_run:
        return AppearanceResult(path, tuple(removed))
    backup = _backup(path)
    _write(path, parser)
    remove_browser_script(runner)
    (runner or subprocess.run)(
        ["qdbus6", "org.kde.KWin", "/KWin", "reconfigure"],
        check=False,
    )
    return AppearanceResult(path, tuple(removed), backup)


def status(path: Path | None = None) -> dict:
    """Return a small summary of installed appearance rules."""
    path = _rules_path(path)
    parser = _read(path)
    groups = [group for group in parser.sections() if group.startswith(RULE_PREFIX)]
    return {
        "path": str(path),
        "enabled": bool(groups),
        "groups": groups,
        "count": len(groups),
    }
