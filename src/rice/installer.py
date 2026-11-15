#!/usr/bin/env python3
"""Install and uninstall the rice desktop configuration.

The installer performs four steps:

1. Preflight the host (Arch/CachyOS, Plasma, graphical session).
2. Install the required and selected packages with pacman or an AUR helper.
3. Copy the runtime tree into ``$XDG_DATA_HOME/rice`` and write the ``rice``
   command wrapper into ``~/.local/bin``.
4. Build the initial configuration from detected hardware and apply it.

Tests only exercise the pure planning helpers and the dry-run paths; the
installer never invokes pacman, an AUR helper, systemctl, KDE, or Noctalia
inside the test suite.
"""

from __future__ import annotations

import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

from .apps import load_catalog, resolve_choices
from .apply import apply_config
from .config import load_config, save_config, validate_config
from .paths import config_home, config_path, data_home, state_home

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_CATALOG = REPO_ROOT / "defaults/apps.toml"
DEFAULT_CONFIG = REPO_ROOT / "defaults/rice.toml"
OS_RELEASE = Path("/etc/os-release")

BASE_PACKAGES = [
    "python",
    "python-tomli-w",
    "python-dbus",
    "python-gobject",
    "noctalia",
    "kscreen",
]

# Packages that are not in the official Arch repositories. The AUR helper is
# resolved before any package work so the installer can stop with instructions
# instead of failing halfway through.
AUR_PACKAGES = {
    "noctalia",
    "gpu-screen-recorder-ui",
    "youtube-music-bin",
    "brave-bin",
    "google-chrome",
    "claude-desktop-bin",
    "claude-code",
    "opencode-bin",
}

ARCH_IDS = {"arch", "archlinux", "cachyos"}
GRAPHICAL_SESSION_TYPES = {"wayland", "x11"}
# Noctalia is installed by the installer itself, so it must not be a preflight
# prerequisite. Only tools shipped by the base Plasma session are probed.
TOOLS = (("plasmashell", ["plasmashell", "--version"]),)
PROBE_TIMEOUT = 10


def package_plan(choices: dict) -> list[str]:
    """Return the package names required for the selected application choices."""
    catalog = load_catalog(APPS_CATALOG)
    apps = resolve_choices(catalog, choices)
    packages = list(BASE_PACKAGES)
    for app in apps.values():
        package = app.get("package")
        if package and package not in packages:
            packages.append(package)
    return packages


def _run(command, dry_run=False, check=True):
    if dry_run:
        print("DRY-RUN:", " ".join(command))
        return
    subprocess.run(command, check=check)


def install_packages(packages: list[str], aur_helper: str, dry_run=False):
    official = [package for package in packages if package not in AUR_PACKAGES]
    aur = [package for package in packages if package in AUR_PACKAGES]
    if official:
        _run(["sudo", "pacman", "-S", "--needed", "--noconfirm", *official], dry_run)
    if aur:
        _run([aur_helper, "-S", "--needed", "--noconfirm", *aur], dry_run)


def install_tree(repo: Path, data_dir: Path, bin_dir: Path, dry_run=False):
    """Copy the runtime tree and write the ``rice`` wrapper."""
    repo = Path(repo)
    data_dir = Path(data_dir)
    bin_dir = Path(bin_dir)
    install_root = data_dir / "rice"
    if dry_run:
        print("DRY-RUN: install", repo, "to", install_root)
        return install_root
    install_root.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(
        repo / "src/rice", install_root / "src/rice", dirs_exist_ok=True, ignore=ignore
    )
    shutil.copytree(
        repo / "templates", install_root / "templates", dirs_exist_ok=True, ignore=ignore
    )
    shutil.copytree(
        repo / "defaults", install_root / "defaults", dirs_exist_ok=True, ignore=ignore
    )
    shutil.copytree(
        repo / "assets", install_root / "assets", dirs_exist_ok=True, ignore=ignore
    )
    plugins = repo / "plugins"
    if plugins.is_dir():
        for plugin in plugins.iterdir():
            if plugin.is_dir():
                shutil.copytree(
                    plugin,
                    data_dir / "noctalia-plugins" / plugin.name,
                    dirs_exist_ok=True,
                )
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "rice"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'RICE_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/rice"\n'
        'export PYTHONPATH="$RICE_DATA/src${PYTHONPATH:+:$PYTHONPATH}"\n'
        'exec python3 -m rice.cli "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return install_root


def _prune_app_references(config: dict, app_ids: set[str]) -> None:
    startup = config.setdefault("startup", {})
    startup["always"] = [app for app in startup.get("always", []) if app in app_ids]
    startup["private"] = [app for app in startup.get("private", []) if app in app_ids]
    config["placement"] = [
        item for item in config.get("placement", []) if item["app"] in app_ids
    ]
    for section in config.get("autostart", {}).values():
        section["apps"] = [app for app in section.get("apps", []) if app in app_ids]


def build_initial_config(choices: dict, dry_run: bool = False) -> dict:
    """Build a validated configuration from the defaults and detected hardware.

    With ``dry_run`` the function never mutates the KDE session: missing
    activities keep an empty id instead of being created.
    """
    from .activities import ensure_activity, list_activities
    from .layouts import choose_layout, default_placements, layout_config
    from .outputs import detect_outputs

    base = deepcopy(load_config(DEFAULT_CONFIG))
    catalog = load_catalog(APPS_CATALOG)
    apps = resolve_choices(catalog, choices)
    base["app"] = [{"id": app_id, **entry} for app_id, entry in apps.items()]

    outputs = detect_outputs()
    if not outputs:
        raise RuntimeError("no connected output detected; connect a display and retry")
    main = next((output for output in outputs if output.primary), outputs[0])
    base["output"] = [
        {
            "id": output.id,
            "role": "main" if output is main else "secondary",
            "connector": output.connector,
            "primary": output.primary,
            "x": output.x,
            "y": output.y,
            "width": output.width,
            "height": output.height,
        }
        for output in outputs
    ]

    preset = choose_layout(outputs)
    base.update(layout_config(preset, outputs))
    base["placement"] = default_placements(preset, apps)
    base["theme"] = {
        "wallpaper_dir": str(Path.home() / "Pictures" / "rice-wallpapers"),
        "outputs": [output.connector for output in outputs],
        "same_image_all_outputs": True,
        "rotation": "hourly",
        "pause_on_fullscreen": True,
        "pause_on_idle": True,
    }

    _prune_app_references(base, set(apps))
    known = list_activities()
    for role, name in (("private", "Private"), ("work", "Work")):
        if dry_run:
            base["activities"][role]["kde_id"] = known.get(name, "")
        else:
            base["activities"][role]["kde_id"] = known.get(name) or ensure_activity(name)
    return base


def _read_os_release(path: Path) -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def preflight(os_release: Path | None = None, environ=None, runner=None) -> None:
    """Verify distribution, tools, and session before touching the system."""
    import os

    environ = os.environ if environ is None else environ
    release_path = Path(os_release or OS_RELEASE)
    try:
        release = _read_os_release(release_path)
    except OSError as error:
        raise RuntimeError(f"cannot read {release_path}: {error}") from None
    identifiers = {release.get("ID", "").lower()}
    identifiers.update(
        item.lower() for item in release.get("ID_LIKE", "").split() if item
    )
    if not identifiers & ARCH_IDS:
        raise RuntimeError(
            "rice targets Arch Linux or CachyOS; /etc/os-release reports "
            f"{release.get('ID') or 'an unknown distribution'}"
        )

    session_type = environ.get("XDG_SESSION_TYPE", "")
    if not (
        session_type in GRAPHICAL_SESSION_TYPES
        or environ.get("WAYLAND_DISPLAY")
        or environ.get("DISPLAY")
    ):
        raise RuntimeError(
            "no graphical session detected; run the installer inside a KDE Plasma 6 session"
        )

    run = runner or subprocess.run
    for label, command in TOOLS:
        try:
            result = run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=PROBE_TIMEOUT,
            )
        except OSError:
            raise RuntimeError(f"{label} is not installed; install it and retry") from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"{label} --version timed out after {PROBE_TIMEOUT}s"
            ) from None
        if getattr(result, "returncode", 0) != 0:
            raise RuntimeError(f"{label} --version failed; check the installation")


class Installer:
    """Run the complete install sequence."""

    def run(self, choices: dict, dry_run: bool = False):
        preflight()
        packages = package_plan(choices)
        helper = shutil.which("paru") or shutil.which("yay")
        if not helper:
            raise RuntimeError(
                "No AUR helper found. Install paru or yay first, then rerun the installer."
            )
        install_packages(packages, helper, dry_run)
        repo = REPO_ROOT
        install_tree(repo, data_home(), Path.home() / ".local/bin", dry_run)
        config = build_initial_config(choices, dry_run=dry_run)
        errors = validate_config(config)
        if errors:
            raise ValueError("; ".join(errors))
        if dry_run:
            print("DRY-RUN: write", config_path())
            return
        save_config(config_path(), config)
        apply_config(config_path())


def _remove(target: Path, dry_run: bool) -> None:
    if dry_run:
        print("DRY-RUN: remove", target)
    elif target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def _remove_wrapper(bin_dir: Path, dry_run: bool) -> None:
    wrapper = Path(bin_dir) / "rice"
    if not wrapper.is_file():
        return
    try:
        owned = "rice.cli" in wrapper.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        owned = False
    if owned:
        _remove(wrapper, dry_run)


def uninstall(dry_run=False, runner=None):
    """Disable rice units and remove only the artifacts the installer created.

    ``$XDG_STATE_HOME/rice`` is kept because it holds apply backups; only the
    runtime and theme state files are removed.
    """
    run = runner or (lambda command: _run(command, dry_run, check=False))
    units = [
        "rice-daemon.service",
        "rice-startup.service",
        "rice-theme-boot.service",
        "rice-theme-hourly.timer",
    ]
    command = ["systemctl", "--user", "disable", "--now", *units]
    if dry_run and runner is None:
        _run(command, dry_run, check=False)
    else:
        try:
            run(command)
        except OSError:
            pass

    targets = [
        data_home() / "rice",
        config_home() / "noctalia" / "config.toml",
        data_home() / "kwin" / "scripts" / "rice-placement",
        config_path(),
        state_home() / "rice" / "runtime.json",
        state_home() / "rice" / "theme-current",
    ]
    targets.extend(sorted((config_home() / "systemd/user").glob("rice-*")))
    for target in targets:
        _remove(target, dry_run)
    _remove_wrapper(Path.home() / ".local/bin", dry_run)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="rice-installer")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--work-browser", choices=["chrome", "firefox"], default="firefox")
    parser.add_argument(
        "--private-browser", choices=["brave", "chromium"], default="chromium"
    )
    parser.add_argument("--claude", choices=["desktop", "code"], default="desktop")
    parser.add_argument(
        "--terminal", choices=["alacritty", "kitty"], default="alacritty"
    )
    parser.add_argument("--youtube-music", action="store_true")
    parser.add_argument("--steam", action="store_true")
    parser.add_argument("--discord", action="store_true")
    parser.add_argument("--opencode", action="store_true")
    parser.add_argument("--gpu-recorder", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)
    if args.uninstall:
        uninstall(dry_run=args.dry_run)
        return 0
    choices = {
        "work_browser": args.work_browser,
        "private_browser": args.private_browser,
        "claude": args.claude,
        "terminal": args.terminal,
        "youtube_music": args.youtube_music,
        "steam": args.steam,
        "discord": args.discord,
        "opencode": args.opencode,
        "gpu_recorder": args.gpu_recorder,
    }
    Installer().run(choices, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
