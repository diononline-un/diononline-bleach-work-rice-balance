import argparse

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rice")
    parser.add_argument("--version", action="version", version=f"rice {__version__}")
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
