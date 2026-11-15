import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from rice.config import validate_config
from rice.generate import generate_kwin, output_roles
from rice.installer import (
    NOCTALIA_GENERATED_MARKER,
    PLUGIN_MARKER,
    build_initial_config,
    install_packages,
    install_tree,
    package_plan,
    preflight,
    uninstall,
)
from rice.outputs import Output

ROOT = Path(__file__).resolve().parents[1]

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


def _triple_outputs_primary_second():
    """Primary is not first in KScreen order; roles follow identity."""
    return [
        Output(
            id="output-1",
            connector="DP-1",
            width=1920,
            height=1080,
            x=0,
            y=0,
            primary=False,
        ),
        Output(
            id="main",
            connector="DP-2",
            width=3440,
            height=1440,
            x=1920,
            y=0,
            primary=True,
        ),
        Output(
            id="output-3",
            connector="HDMI-A-1",
            width=1080,
            height=1920,
            x=5360,
            y=0,
            primary=False,
        ),
    ]


def test_build_initial_config_assigns_roles_independent_of_output_order(monkeypatch):
    monkeypatch.setattr("rice.outputs.detect_outputs", _triple_outputs_primary_second)
    monkeypatch.setattr(
        "rice.activities.list_activities",
        lambda: {"Private": "private-id", "Work": "work-id"},
    )

    config = build_initial_config(CHOICES)

    assert validate_config(config) == []
    roles = {output["connector"]: output["role"] for output in config["output"]}
    assert roles == {"DP-2": "main", "DP-1": "side", "HDMI-A-1": "portrait"}
    # Stable ids and geometry survive role assignment.
    by_connector = {output["connector"]: output for output in config["output"]}
    assert by_connector["DP-2"]["id"] == "main"
    assert by_connector["DP-1"]["id"] == "output-1"
    assert by_connector["HDMI-A-1"]["id"] == "output-3"
    assert by_connector["DP-1"]["x"] == 0
    assert by_connector["DP-2"]["width"] == 3440
    assert "secondary" not in {output["role"] for output in config["output"]}

    # The generated KWin shortcut block resolves move targets from these roles.
    assert output_roles(config) == [
        {"role": "side", "connector": "DP-1"},
        {"role": "main", "connector": "DP-2"},
        {"role": "portrait", "connector": "HDMI-A-1"},
    ]
    js = generate_kwin(config)
    for role, connector in (
        ("main", "DP-2"),
        ("side", "DP-1"),
        ("portrait", "HDMI-A-1"),
    ):
        assert f'"role": "{role}"' in js
        assert f'"connector": "{connector}"' in js


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


def test_build_initial_config_dry_run_skips_activity_creation(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr("rice.outputs.detect_outputs", _fake_outputs)
    monkeypatch.setattr(
        "rice.activities.list_activities", lambda: {"Private": "existing-id"}
    )

    def fail(name):
        raise AssertionError("dry-run must not create KDE activities")

    monkeypatch.setattr("rice.activities.ensure_activity", fail)

    config = build_initial_config(CHOICES, dry_run=True)

    assert config["activities"]["private"]["kde_id"] == "existing-id"
    assert config["activities"]["work"]["kde_id"] == ""
    assert not (tmp_path / "config/rice/rice.toml").exists()


def test_build_initial_config_rejects_invalid_choices(monkeypatch):
    monkeypatch.setattr("rice.outputs.detect_outputs", _fake_outputs)
    choices = dict(CHOICES, terminal="xterm")
    with pytest.raises(ValueError):
        build_initial_config(choices)


def _make_repo(root: Path, plugins: bool = False) -> Path:
    (root / "src/rice").mkdir(parents=True)
    (root / "src/rice/__init__.py").write_text("", encoding="utf-8")
    (root / "src/web").mkdir(parents=True)
    (root / "src/web/index.html").write_text("ok", encoding="utf-8")
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


def test_install_tree_copies_web_assets(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    (repo / "src/web/app.js").write_text("// app\n", encoding="utf-8")
    (repo / "src/web/style.css").write_text(":root {}\n", encoding="utf-8")

    install_tree(repo, tmp_path / "data", tmp_path / "bin")

    for name in ("index.html", "app.js", "style.css"):
        assert (tmp_path / "data/rice/src/web" / name).is_file(), name


def test_install_tree_installs_rice_and_rice_config_launchers(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    bin_dir = tmp_path / "bin"

    install_tree(repo, tmp_path / "data", bin_dir)

    expected = {
        "rice": "python3 -m rice.cli",
        "rice-config": "python3 -m rice.web",
    }
    for name, module in expected.items():
        launcher = bin_dir / name
        text = launcher.read_text(encoding="utf-8")
        assert module in text, name
        assert "XDG_DATA_HOME" in text, name
        assert "/home/" not in text, name
        assert launcher.stat().st_mode & stat.S_IXUSR, name


def test_installed_web_module_resolves_assets_and_catalog(tmp_path: Path):
    data_dir = tmp_path / "data"
    install_tree(ROOT, data_dir, tmp_path / "bin")

    env = dict(os.environ, PYTHONPATH=str(data_dir / "rice/src"))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import rice.web as web; print(web.WEB_ROOT); print(web.CATALOG_PATH)",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    web_root, catalog = result.stdout.split()
    assert Path(web_root) == data_dir / "rice/src/web"
    assert (Path(web_root) / "index.html").is_file()
    assert Path(catalog) == data_dir / "rice/defaults/apps.toml"


def test_install_tree_dry_run_writes_no_launchers(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    data_dir = tmp_path / "data"
    bin_dir = tmp_path / "bin"

    install_tree(repo, data_dir, bin_dir, dry_run=True)

    assert not (data_dir / "rice").exists()
    assert not (bin_dir / "rice").exists()
    assert not (bin_dir / "rice-config").exists()


def test_install_tree_copies_plugins_when_present(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo", plugins=True)
    data_dir = tmp_path / "share"

    install_tree(repo, data_dir, tmp_path / "bin")

    copied = data_dir / "noctalia-plugins/example/plugin.toml"
    assert copied.is_file()
    marker = data_dir / "noctalia-plugins/example" / PLUGIN_MARKER
    assert marker.is_file()
    assert "Installed by rice" in marker.read_text(encoding="utf-8")


def test_install_tree_refuses_unmarked_existing_plugin_directory(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo", plugins=True)
    data_dir = tmp_path / "share"
    user_plugin = data_dir / "noctalia-plugins/example"
    user_plugin.mkdir(parents=True)
    user_file = user_plugin / "plugin.toml"
    user_file.write_text("# my own plugin\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="user-owned plugin directory") as error:
        install_tree(repo, data_dir, tmp_path / "bin")

    assert str(user_plugin) in str(error.value)
    assert user_file.read_text(encoding="utf-8") == "# my own plugin\n"
    assert not (user_plugin / PLUGIN_MARKER).exists()
    assert not (data_dir / "rice").exists()


def test_real_repo_plugins_and_noctalia_base_are_copied(tmp_path: Path):
    for name in ("themes", "profile", "cheatsheet", "media"):
        assert (ROOT / "plugins" / name / "plugin.toml").is_file()
    assert (ROOT / "defaults/noctalia/config.toml").is_file()
    assert (ROOT / "defaults/noctalia/media.json").is_file()

    data_dir = tmp_path / "share"
    install_root = install_tree(ROOT, data_dir, tmp_path / "bin")

    assert (install_root / "defaults/noctalia/config.toml").is_file()
    assert (install_root / "defaults/noctalia/media.json").is_file()
    for asset in ("index.html", "app.js", "style.css"):
        assert (install_root / "src/web" / asset).is_file(), asset
    for template in (ROOT / "templates").rglob("*"):
        if template.is_file():
            installed = install_root / "templates" / template.relative_to(ROOT / "templates")
            assert installed.is_file(), f"missing installed template {installed}"
    # Sanity check that the template loop saw the expected runtime units.
    assert (install_root / "templates/systemd/rice-shortcuts.service.in").is_file()
    assert (install_root / "templates/kwin/main.js.in").is_file()
    assert (install_root / "templates/kwin/arrange.js.in").is_file()
    for name, files in (
        ("themes", ("plugin.toml", "panel.luau")),
        ("profile", ("plugin.toml", "widget.luau")),
        ("cheatsheet", ("plugin.toml", "panel.luau")),
        (
            "media",
            (
                "plugin.toml",
                "service.luau",
                "desktop.luau",
                "player_panel.luau",
                "queue_panel.luau",
            ),
        ),
    ):
        for filename in files:
            copied = data_dir / "noctalia-plugins" / name / filename
            assert copied.is_file(), f"missing installed plugin file {copied}"
        marker = data_dir / "noctalia-plugins" / name / PLUGIN_MARKER
        assert marker.is_file(), f"missing ownership marker for {name}"


def test_install_tree_dry_run_changes_nothing(tmp_path: Path):
    repo = _make_repo(tmp_path / "repo")
    data_dir = tmp_path / "share"
    bin_dir = tmp_path / "bin"

    install_root = install_tree(repo, data_dir, bin_dir, dry_run=True)

    assert install_root == data_dir / "rice"
    assert not install_root.exists()
    assert not bin_dir.exists()


def test_install_packages_splits_official_and_aur(monkeypatch):
    calls = []

    def fake_run(command, dry_run=False):
        calls.append(list(command))

    monkeypatch.setattr("rice.installer._run", fake_run)

    install_packages(["firefox", "noctalia", "python"], "paru")

    assert calls == [
        [
            "sudo",
            "pacman",
            "-S",
            "--needed",
            "--noconfirm",
            "firefox",
            "python",
        ],
        ["paru", "-S", "--needed", "--noconfirm", "noctalia"],
    ]


def test_uninstall_removes_only_rice_artifacts(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    data = tmp_path / "data"
    config = tmp_path / "config"
    state = tmp_path / "state"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))

    (data / "rice/src/rice").mkdir(parents=True)
    (data / "kwin/scripts/rice-placement/contents/code").mkdir(parents=True)
    (data / "kwin/scripts/rice-placement/contents/code/main.js").write_text(
        "", encoding="utf-8"
    )
    (data / "noctalia-plugins/themes").mkdir(parents=True)
    (data / "noctalia-plugins/themes").joinpath(PLUGIN_MARKER).write_text(
        "installed by rice\n", encoding="utf-8"
    )
    (data / "noctalia-plugins/themes/plugin.toml").write_text("", encoding="utf-8")
    (data / "noctalia-plugins/other").mkdir(parents=True)
    (data / "noctalia-plugins/other/plugin.toml").write_text("", encoding="utf-8")
    (config / "noctalia").mkdir(parents=True)
    (config / "noctalia/config.toml").write_text(
        NOCTALIA_GENERATED_MARKER + "\n", encoding="utf-8"
    )
    (config / "noctalia/other.toml").write_text("", encoding="utf-8")
    (config / "noctalia/media.json").write_text("{}", encoding="utf-8")
    (config / "rice").mkdir()
    (config / "rice/rice.toml").write_text("", encoding="utf-8")
    (state / "rice/backups").mkdir(parents=True)
    (state / "rice/runtime.json").write_text("{}", encoding="utf-8")
    (state / "rice/theme-current").write_text("", encoding="utf-8")
    (state / "rice/backups/keep.tar").write_text("backup", encoding="utf-8")
    (config / "systemd/user").mkdir(parents=True)
    for unit in (
        "rice-daemon.service",
        "rice-startup.service",
        "rice-theme-boot.service",
        "rice-theme-hourly.timer",
        "rice-shortcuts.service",
    ):
        (config / "systemd/user" / unit).write_text("", encoding="utf-8")
    (config / "systemd/user/other.service").write_text("", encoding="utf-8")
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
            "rice-theme-boot.service",
            "rice-theme-hourly.timer",
            "rice-shortcuts.service",
        ]
    ]
    assert not (data / "rice").exists()
    assert not (data / "kwin/scripts/rice-placement").exists()
    assert not (data / "noctalia-plugins/themes").exists()
    assert (data / "noctalia-plugins/other/plugin.toml").is_file()
    assert not (config / "noctalia/config.toml").exists()
    assert (config / "noctalia/other.toml").is_file()
    assert (config / "noctalia/media.json").is_file()
    assert not (config / "rice/rice.toml").exists()
    assert not (state / "rice/runtime.json").exists()
    assert not (state / "rice/theme-current").exists()
    assert (state / "rice/backups/keep.tar").is_file()
    assert not list((config / "systemd/user").glob("rice-*"))
    assert (config / "systemd/user/other.service").is_file()
    assert not wrapper.exists()
    assert (wallpapers / "keep.png").is_file()


def test_uninstall_removes_rice_config_launcher_and_web_assets(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    data = tmp_path / "data"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True)
    rice_launcher = bin_dir / "rice"
    rice_launcher.write_text("exec python3 -m rice.cli \"$@\"\n", encoding="utf-8")
    config_launcher = bin_dir / "rice-config"
    config_launcher.write_text("exec python3 -m rice.web \"$@\"\n", encoding="utf-8")
    web_asset = data / "rice/src/web/index.html"
    web_asset.parent.mkdir(parents=True)
    web_asset.write_text("ok", encoding="utf-8")
    (data / "rice/src/rice").mkdir(parents=True)

    uninstall(runner=lambda command: None)

    assert not rice_launcher.exists()
    assert not config_launcher.exists()
    assert not (data / "rice").exists()


def test_uninstall_keeps_user_rice_config_launcher(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True)
    user_launcher = bin_dir / "rice-config"
    user_launcher.write_text("#!/bin/sh\necho my own configurator\n", encoding="utf-8")

    uninstall(runner=lambda command: None)

    assert user_launcher.is_file()
    assert "my own configurator" in user_launcher.read_text(encoding="utf-8")


def test_uninstall_keeps_hand_written_noctalia_config(tmp_path: Path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    hand_written = config / "noctalia/config.toml"
    hand_written.parent.mkdir(parents=True)
    hand_written.write_text("[bar]\norder = [\"custom\"]\n", encoding="utf-8")
    backup = tmp_path / "state/rice/backups/20260101-000000/config.toml"
    backup.parent.mkdir(parents=True)
    backup.write_text("older\n", encoding="utf-8")

    uninstall(runner=lambda command: None)

    assert hand_written.read_text(encoding="utf-8") == "[bar]\norder = [\"custom\"]\n"


def test_uninstall_preserves_unmarked_user_plugin_with_rice_name(
    tmp_path: Path, monkeypatch
):
    data = tmp_path / "data"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    user_plugin = data / "noctalia-plugins/themes"
    user_file = user_plugin / "plugin.toml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text("# user theme plugin\n", encoding="utf-8")

    uninstall(runner=lambda command: None)

    assert user_file.read_text(encoding="utf-8") == "# user theme plugin\n"
    assert not (user_plugin / PLUGIN_MARKER).exists()


def test_uninstall_removes_empty_plugin_directory(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    plugin = data / "noctalia-plugins/media"
    plugin.mkdir(parents=True)
    (plugin / PLUGIN_MARKER).write_text("installed by rice\n", encoding="utf-8")
    (plugin / "plugin.toml").write_text("", encoding="utf-8")

    uninstall(runner=lambda command: None)

    assert not (data / "noctalia-plugins").exists()


def test_uninstall_dry_run_changes_nothing(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "data/rice").mkdir(parents=True)

    uninstall(dry_run=True, runner=lambda command: None)

    assert (tmp_path / "data/rice").is_dir()
    assert "DRY-RUN" in capsys.readouterr().out


def test_uninstall_restores_preexisting_noctalia_config(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    config = tmp_path / "config"
    state = tmp_path / "state"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))

    generated = config / "noctalia/config.toml"
    generated.parent.mkdir(parents=True)
    generated.write_text(NOCTALIA_GENERATED_MARKER + "\n[bar]\n", encoding="utf-8")
    original = state / "rice/backups/20260101-000000/config.toml"
    original.parent.mkdir(parents=True)
    original.write_text("original user settings\n", encoding="utf-8")
    later = state / "rice/backups/20260102-000000/config.toml"
    later.parent.mkdir(parents=True)
    later.write_text(NOCTALIA_GENERATED_MARKER + "\n[bar]\n", encoding="utf-8")

    uninstall(runner=lambda command: None)

    assert generated.read_text(encoding="utf-8") == "original user settings\n"
    assert original.is_file()
    assert later.is_file()


def test_uninstall_removes_generated_config_without_user_backup(
    tmp_path: Path, monkeypatch
):
    config = tmp_path / "config"
    state = tmp_path / "state"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))

    generated = config / "noctalia/config.toml"
    generated.parent.mkdir(parents=True)
    generated.write_text(NOCTALIA_GENERATED_MARKER + "\n", encoding="utf-8")
    backup = state / "rice/backups/20260101-000000/config.toml"
    backup.parent.mkdir(parents=True)
    backup.write_text(NOCTALIA_GENERATED_MARKER + "\n", encoding="utf-8")

    uninstall(runner=lambda command: None)

    assert not generated.exists()
    assert backup.is_file()


def test_preflight_accepts_arch_family(tmp_path: Path):
    release = tmp_path / "os-release"
    release.write_text(
        'ID=cachyos\nID_LIKE=arch\nPRETTY_NAME="CachyOS"\n', encoding="utf-8"
    )
    probes = []

    def runner(command, **kwargs):
        probes.append((command, kwargs.get("timeout")))
        return type("Result", (), {"returncode": 0})()

    preflight(
        os_release=release,
        environ={"XDG_SESSION_TYPE": "wayland"},
        runner=runner,
    )

    assert probes == [(["plasmashell", "--version"], 10)]


def test_preflight_does_not_require_noctalia_before_install(tmp_path: Path):
    release = tmp_path / "os-release"
    release.write_text("ID=arch\n", encoding="utf-8")
    probed = []

    def runner(command, **kwargs):
        probed.extend(command)
        return type("Result", (), {"returncode": 0})()

    preflight(os_release=release, environ={"DISPLAY": ":0"}, runner=runner)

    assert "noctalia" not in probed


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
