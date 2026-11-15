import argparse
import json
import subprocess
import sys

from . import __version__
from .activities import current_activity
from .paths import state_home

CHEATSHEET_PANEL = "rice/cheatsheet:panel"


def run_apply(args):
    from .apply import apply_config
    from .paths import config_path

    apply_config(config_path(), dry_run=args.dry_run)
    return 0


def _runtime():
    return json.loads(
        (state_home() / "rice/runtime.json").read_text(encoding="utf-8")
    )


def run_startup_command(args):
    from .startup import run_startup

    run_startup(_runtime())
    return 0


def run_doctor(args):
    import shutil

    from .config import load_config, validate_config
    from .outputs import detect_outputs
    from .paths import config_path

    errors = []
    if not shutil.which("noctalia"):
        errors.append("noctalia is not installed")
    if not shutil.which("qdbus6"):
        errors.append("qdbus6 is not installed")
    try:
        if not detect_outputs():
            errors.append("no detected outputs")
    except Exception as exc:
        errors.append(f"output detection failed: {exc}")
    try:
        errors.extend(validate_config(load_config(config_path())))
    except Exception as exc:
        errors.append(f"config load failed: {exc}")
    print("\n".join(errors) if errors else "rice doctor: OK")
    return 1 if errors else 0


def run_activity_command(args):
    from .activities import switch_activity
    from .startup import run_autostart

    runtime = _runtime()
    switch_activity(runtime["activities"][args.role]["kde_id"])
    run_autostart(runtime, args.role)
    return 0


def run_daemon(args):
    from . import daemon

    daemon.main()
    return 0


def run_cheatsheet(args):
    subprocess.run(
        ["noctalia", "msg", "panel-toggle", CHEATSHEET_PANEL], check=True
    )
    return 0


def run_quickstart(args):
    from .startup import run_autostart, run_startup

    runtime = _runtime()
    roles = {
        entry["kde_id"]: role
        for role, entry in runtime.get("activities", {}).items()
        if isinstance(entry, dict) and entry.get("kde_id")
    }
    role = roles.get(current_activity().strip())
    if role is None:
        raise RuntimeError(
            "current KDE activity is not mapped to a rice role; run `rice apply` first"
        )
    if role == "private":
        run_startup(runtime)
    else:
        run_autostart(runtime, role)
    return 0


def run_arrange(args):
    subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.rice.Rice",
            "--object-path",
            "/Rice",
            "--method",
            "org.rice.Rice.ReapplyPlacement",
        ],
        check=True,
    )
    return 0


def run_shortcuts(args):
    from .shortcuts import disable_conflicts

    cleared = disable_conflicts()
    if not cleared:
        print("rice shortcuts: no conflicting KDE shortcuts found")
    else:
        for entry in cleared:
            print(f"rice shortcuts: disabled {entry}")
    return 0


def run_theme_command(args):
    from pathlib import Path

    from .theme import _apply, boot_theme, hourly_theme, list_wallpapers
    from .theme import current_theme, next_theme, previous_theme, refresh_cache
    from .theme import set_theme, toggle_panel

    if args.value == "panel":
        toggle_panel()
        return 0
    if args.value == "refresh":
        refresh_cache(_runtime())
        return 0
    if args.value == "status":
        path = current_theme()
        if path is not None:
            print(path)
        return 0

    if args.value == "set" and not args.path:
        raise ValueError("theme set requires an image path")

    runtime = _runtime()
    if args.value == "set":
        set_theme(runtime, args.path)
    elif args.value == "boot":
        boot_theme(runtime)
    elif args.value == "hourly":
        hourly_theme(runtime)
    elif args.value == "random":
        import random

        directory = Path(runtime["theme"]["wallpaper_dir"]).expanduser()
        files = list_wallpapers(directory)
        if files:
            _apply(runtime, random.choice(files))
    elif args.value == "next":
        next_theme(runtime)
    else:
        previous_theme(runtime)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rice")
    parser.add_argument("--version", action="version", version=f"rice {__version__}")
    sub = parser.add_subparsers(dest="command")

    apply_parser = sub.add_parser("apply", help="write generated rice configuration")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.set_defaults(func=run_apply)

    startup_parser = sub.add_parser("startup", help="launch startup applications")
    startup_parser.set_defaults(func=run_startup_command)

    activity_parser = sub.add_parser("activity", help="switch KDE activity")
    activity_parser.add_argument("role", choices=["private", "work"])
    activity_parser.set_defaults(func=run_activity_command)

    daemon_parser = sub.add_parser("daemon", help="run the rice D-Bus daemon")
    daemon_parser.set_defaults(func=run_daemon)

    cheatsheet_parser = sub.add_parser(
        "cheatsheet", help="toggle the shortcut cheatsheet panel"
    )
    cheatsheet_parser.set_defaults(func=run_cheatsheet)

    quickstart_parser = sub.add_parser(
        "quickstart", help="launch the app set for the current activity"
    )
    quickstart_parser.set_defaults(func=run_quickstart)

    arrange_parser = sub.add_parser(
        "arrange", help="reapply the window layout to the current activity"
    )
    arrange_parser.set_defaults(func=run_arrange)

    doctor_parser = sub.add_parser("doctor", help="check runtime dependencies")
    doctor_parser.set_defaults(func=run_doctor)

    shortcuts_parser = sub.add_parser(
        "shortcuts", help="manage KDE global shortcuts"
    )
    shortcuts_sub = shortcuts_parser.add_subparsers(dest="shortcut_action")
    disable_parser = shortcuts_sub.add_parser(
        "disable-conflicts", help="clear conflicting KDE global shortcuts"
    )
    disable_parser.set_defaults(func=run_shortcuts)

    theme_parser = sub.add_parser("theme", help="manage wallpapers")
    theme_parser.add_argument(
        "value",
        choices=[
            "next",
            "previous",
            "boot",
            "hourly",
            "random",
            "set",
            "refresh",
            "panel",
            "status",
        ],
    )
    theme_parser.add_argument("path", nargs="?", help="image path for `theme set`")
    theme_parser.set_defaults(func=run_theme_command)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    if not getattr(args, "func", None):
        parser.parse_args([args.command, "--help"])
        return 0
    try:
        return args.func(args) or 0
    except (
        ValueError,
        FileNotFoundError,
        RuntimeError,
        KeyError,
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        # Operational failures reach the user as one clean line. argparse keeps
        # its own SystemExit handling for usage errors.
        print(f"rice: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
