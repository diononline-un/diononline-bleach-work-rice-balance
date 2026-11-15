"""KWin appearance profile: solid application windows.

This module removes rice-owned opacity rules. The rice shell (Noctalia) keeps
its own glass styling; application windows use the compositor default of 100%
opacity.
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

from .paths import config_home, state_home

RULE_PREFIX = "rice-appearance-"
RULE_ORDER = "General"


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


def apply_rules(
    path: Path | None = None,
    *,
    dry_run: bool = False,
    runner=None,
) -> AppearanceResult:
    """Remove legacy rice opacity rules; application windows stay solid."""
    path = _rules_path(path)
    parser = _read(path)
    _remove_managed(parser)
    groups: list[str] = []
    if dry_run:
        return AppearanceResult(path, tuple(groups))
    backup = _backup(path)
    _write(path, parser)
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
