import argparse
import json
import sys

from . import __version__
from .paths import state_home


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


def run_theme_command(args):
    from pathlib import Path

    from .theme import _apply, boot_theme, hourly_theme, list_wallpapers
    from .theme import next_theme, previous_theme

    runtime = _runtime()
    if args.value == "boot":
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

    doctor_parser = sub.add_parser("doctor", help="check runtime dependencies")
    doctor_parser.set_defaults(func=run_doctor)

    theme_parser = sub.add_parser("theme", help="manage wallpapers")
    theme_parser.add_argument(
        "value", choices=["next", "previous", "boot", "hourly", "random"]
    )
    theme_parser.set_defaults(func=run_theme_command)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args) or 0
    except (ValueError, FileNotFoundError, RuntimeError, KeyError, OSError) as exc:
        # Operational failures reach the user as one clean line. argparse keeps
        # its own SystemExit handling for usage errors.
        print(f"rice: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
