import os
from pathlib import Path


def xdg(env: str, fallback: str) -> Path:
    return Path(os.environ.get(env, str(Path.home() / fallback)))


def config_home() -> Path:
    return xdg("XDG_CONFIG_HOME", ".config")


def data_home() -> Path:
    return xdg("XDG_DATA_HOME", ".local/share")


def state_home() -> Path:
    return xdg("XDG_STATE_HOME", ".local/state")


def cache_home() -> Path:
    return xdg("XDG_CACHE_HOME", ".cache")


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user"))


def config_path() -> Path:
    return config_home() / "rice" / "rice.toml"
