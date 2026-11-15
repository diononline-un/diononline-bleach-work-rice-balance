#!/usr/bin/env python3
"""Write generated rice artifacts into XDG directories."""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import load_config, validate_config
from .generate import (
    generate_kwin,
    generate_noctalia,
    generate_runtime,
    generate_systemd,
)
from .paths import config_home, data_home, state_home

ROOT = Path(__file__).resolve().parents[2]

RELOAD_COMMANDS = (
    ("systemctl", "--user", "daemon-reload"),
    (
        "systemctl",
        "--user",
        "enable",
        "--now",
        "rice-daemon.service",
        "rice-startup.service",
    ),
    (
        "kwriteconfig6",
        "--file",
        "kwinrc",
        "--group",
        "Plugins",
        "--key",
        "rice-placementEnabled",
        "true",
    ),
    ("qdbus6", "org.kde.KWin", "/KWin", "reconfigure"),
    ("noctalia", "msg", "config-reload"),
)


@dataclass
class ApplyResult:
    changed: list[Path]
    skipped: list[str]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _backup_root() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = state_home() / "rice" / "backups" / stamp
    suffix = 1
    while root.exists():
        root = state_home() / "rice" / "backups" / f"{stamp}-{suffix}"
        suffix += 1
    root.mkdir(parents=True)
    return root


def backup_paths(paths: list[Path]) -> Path:
    root = _backup_root()
    for path in paths:
        if path.is_file():
            shutil.copy2(path, root / path.name)
    return root


def _metadata() -> str:
    return json.dumps(
        {
            "KPlugin": {
                "Id": "rice-placement",
                "Name": "Rice Placement",
                "Description": "Rice zone-based window placement",
                "Version": __version__,
                "EnabledByDefault": False,
            },
            "X-Plasma-API": "javascript",
            "X-Plasma-MainScript": "code/main.js",
        },
        indent=2,
    )


def _generated(config: dict) -> dict[Path, str]:
    kwin_dir = data_home() / "kwin/scripts/rice-placement"
    noir_dir = config_home() / "noctalia"
    unit_dir = config_home() / "systemd/user"
    runtime_path = state_home() / "rice/runtime.json"
    generated = {
        kwin_dir / "contents/code/main.js": generate_kwin(config),
        kwin_dir / "metadata.json": _metadata(),
        noir_dir / "config.toml": generate_noctalia(config),
        runtime_path: json.dumps(generate_runtime(config), indent=2),
    }
    for name, content in generate_systemd(config, ROOT).items():
        generated[unit_dir / name] = content
    return generated


def _run(*command: str) -> None:
    subprocess.run(command, check=False)


def apply_config(config_path: Path, dry_run: bool = False, runner=None) -> ApplyResult:
    config = load_config(Path(config_path))
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))

    generated = _generated(config)
    if dry_run:
        return ApplyResult(list(generated), [])

    backup_paths(list(generated))
    for path, content in generated.items():
        _write(path, content)

    run = runner or _run
    for command in RELOAD_COMMANDS:
        run(*command)
    return ApplyResult(list(generated), [])
