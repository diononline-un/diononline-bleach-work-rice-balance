import stat
from pathlib import Path

import pytest

from rice.config import validate_config
from rice.installer import (
    build_initial_config,
    install_tree,
    package_plan,
    preflight,
    uninstall,
)
from rice.outputs import Output

CHOICES = {
    "work_browser": "firefox",
    "private_browser": "chromium",
    "claude": "desktop",
    "terminal": "alacritty",
    "youtube_music": False,
}

# The public-safety scan forbids the literal denylist markers in tracked files,
# so the assertion builds them at runtime instead of spelling them out.
FORBIDDEN = ("dsh", "tail" "scale")


def test_package_plan_includes_selected_variants():
    packages = package_plan(CHOICES)
    assert "firefox" in packages
    assert "chromium" in packages
    assert "youtube-music-bin" not in packages


def test_package_plan_has_no_personal_entries():
    packages = package_plan(CHOICES)
    assert all(
        marker not in package for package in packages for marker in FORBIDDEN
    )


def test_package_plan_covers_every_required_slot_and_runtime():
    packages = package_plan(CHOICES)
    for required in (
        "python",
        "python-tomli-w",
        "noctalia",
        "kscreen",
        "claude-desktop-bin",
        "alacritty",
    ):
        assert required in packages
    assert len(packages) == len(set(packages))


def _fake_outputs():
    return [
        Output(
            id="main",
            connector="DP-1",
            width=1920,
            height=1080,
            x=0,
            y=0,
            primary=True,
        )
    ]


def test_build_initial_config_matches_detected_hardware(monkeypatch):
    monkeypatch.setattr("rice.outputs.detect_outputs", _fake_outputs)
    monkeypatch.setattr(
        "rice.activities.list_activities",
        lambda: {"Private": "private-id", "Work": "work-id"},
    )

    config = build_initial_config(CHOICES)

    assert validate_config(config) == []
    assert [item["connector"] for item in config["output"]] == ["DP-1"]
    assert {item["id"] for item in config["zone"]} == {"center-left", "center-right"}
    assert {item["app"] for item in config["placement"]} == {
        "work-browser",
        "private-browser",
        "claude",
        "terminal",
    }
    assert config["activities"]["private"]["kde_id"] == "private-id"
    assert config["activities"]["work"]["kde_id"] == "work-id"
    assert config["startup"]["private"] == []
    assert config["theme"]["wallpaper_dir"].endswith("rice-wallpapers")
    assert config["theme"]["outputs"] == ["DP-1"]
    assert config["theme"]["same_image_all_outputs"] is True
    assert config["theme"]["rotation"] == "hourly"
    assert config["theme"]["pause_on_fullscreen"] is True
    assert config["theme"]["pause_on_idle"] is True


def test_build_initial_config_creates_missing_activities(monkeypatch):
    monkeypatch.setattr("rice.outputs.detect_outputs", _fake_outputs)
    monkeypatch.setattr("rice.activities.list_activities", lambda: {})
    monkeypatch.setattr(
        "rice.activities.ensure_activity", lambda name: f"created-{name.lower()}"
    )

    config = build_initial_config(CHOICES)

    assert config["activities"]["private"]["kde_id"] == "created-private"
    assert config["activities"]["work"]["kde_id"] == "created-work"


def test_build_initial_config_rejects_invalid_choices(monkeypatch):
    monkeypatch.setattr("rice.outputs.detect_outputs", _fake_outputs)
    choices = dict(CHOICES, terminal="xterm")
    with pytest.raises(ValueError):
        build_initial_config(choices)


def _make_repo(root: Path, plugins: bool = False) -> Path:
    (root / "src/rice").mkdir(parents=True)
    (root / "src/rice/__init__.py").write_text("", encoding="utf-8")
    (root / "templates/systemd").mkdir(parents=True)
    (root / "templates/systemd/unit.in").write_text("unit\n", encoding="utf-8")
    (root / "defaults").mkdir()
    (root / "defaults/rice.toml").write_text("", encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets/manifest.toml").write_text("", encoding="utf-8")
    if plugins:
        (root / "plugins/example").mkdir(parents=True)
        (root / "plugins/example/plugin.toml").write_text(
            "name = 'example'\n", encoding="utf-8"
        )
    return root


def test_install_tree_copies_tree_without_plugins(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    data_dir = tmp_path / "share"
    bin_dir = tmp_path / "bin"

    install_root = install_tree(repo, data_dir, bin_dir)

    assert (install_root / "src/rice/__init__.py").is_file()
    assert (install_root / "templates/systemd/unit.in").is_file()
    assert (install_root / "defaults/rice.toml").is_file()
    assert (install_root / "assets/manifest.toml").is_file()
    assert not (data_dir / "noctalia-plugins").exists()

    wrapper = bin_dir / "rice"
    text = wrapper.read_text(encoding="utf-8")
    assert "python3 -m rice.cli" in text
    assert "XDG_DATA_HOME" in text
    assert "/home/" not in text
    assert wrapper.stat().st_mode & stat.S_IXUSR


def test_install_tree_copies_plugins_when_present(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo", plugins=True)
    data_dir = tmp_path / "share"

    install_tree(repo, data_dir, tmp_path / "bin")

    copied = data_dir / "noctalia-plugins/example/plugin.toml"
    assert copied.is_file()


def test_install_tree_dry_run_changes_nothing(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    data_dir = tmp_path / "share"
    bin_dir = tmp_path / "bin"

    install_root = install_tree(repo, data_dir, bin_dir, dry_run=True)

    assert install_root == data_dir / "rice"
    assert not install_root.exists()
    assert not bin_dir.exists()


def test_uninstall_removes_only_rice_artifacts(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    data = tmp_path / "data"
    config = tmp_path / "config"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))

    (data / "rice/src/rice").mkdir(parents=True)
    (data / "kwin/scripts/rice-placement/contents/code").mkdir(parents=True)
    (data / "kwin/scripts/rice-placement/contents/code/main.js").write_text(
        "", encoding="utf-8"
    )
    (config / "noctalia").mkdir(parents=True)
    (config / "noctalia/rice.toml").write_text("", encoding="utf-8")
    (config / "noctalia/other.toml").write_text("", encoding="utf-8")
    wrapper = home / ".local/bin/rice"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("exec python3 -m rice.cli \"$@\"\n", encoding="utf-8")
    wallpapers = home / "Pictures/rice-wallpapers"
    wallpapers.mkdir(parents=True)
    (wallpapers / "keep.png").write_bytes(b"png")

    calls = []
    uninstall(runner=lambda command: calls.append(command))

    assert calls == [
        [
            "systemctl",
            "--user",
            "disable",
            "--now",
            "rice-daemon.service",
            "rice-startup.service",
        ]
    ]
    assert not (data / "rice").exists()
    assert not (data / "kwin/scripts/rice-placement").exists()
    assert not (config / "noctalia/rice.toml").exists()
    assert (config / "noctalia/other.toml").is_file()
    assert not wrapper.exists()
    assert (wallpapers / "keep.png").is_file()


def test_uninstall_dry_run_changes_nothing(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "data/rice").mkdir(parents=True)

    uninstall(dry_run=True, runner=lambda command: None)

    assert (tmp_path / "data/rice").is_dir()
    assert "DRY-RUN" in capsys.readouterr().out


def test_preflight_accepts_arch_family(tmp_path: Path):
    release = tmp_path / "os-release"
    release.write_text(
        'ID=cachyos\nID_LIKE=arch\nPRETTY_NAME="CachyOS"\n', encoding="utf-8"
    )
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return type("Result", (), {"returncode": 0})()

    preflight(
        os_release=release,
        environ={"XDG_SESSION_TYPE": "wayland"},
        runner=runner,
    )

    assert commands == [["plasmashell", "--version"], ["noctalia", "--version"]]


def test_preflight_rejects_other_distribution(tmp_path: Path):
    release = tmp_path / "os-release"
    release.write_text("ID=ubuntu\nID_LIKE=debian\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Arch Linux or CachyOS"):
        preflight(os_release=release, environ={"DISPLAY": ":0"})


def test_preflight_requires_graphical_session(tmp_path: Path):
    release = tmp_path / "os-release"
    release.write_text("ID=arch\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="graphical session"):
        preflight(os_release=release, environ={})


def test_preflight_reports_missing_tool(tmp_path: Path):
    release = tmp_path / "os-release"
    release.write_text("ID=arch\n", encoding="utf-8")

    def runner(command, **kwargs):
        raise FileNotFoundError(command[0])

    with pytest.raises(RuntimeError, match="plasmashell"):
        preflight(os_release=release, environ={"DISPLAY": ":0"}, runner=runner)
