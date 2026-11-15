import configparser
from pathlib import Path

from rice.appearance import (
    RULE_PREFIX,
    apply_rules,
    remove_rules,
    status,
)


def _rules(path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(path.parent / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(path.parent / "state"))
    return path


def _parser(path: Path):
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def test_apply_preserves_existing_rules_and_adds_exceptions(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    path.write_text(
        "[General]\nOrder=existing\n\n[existing]\nDescription=Keep me\ntypes=1\n",
        encoding="utf-8",
    )
    result = apply_rules(path, runner=lambda *args, **kwargs: None)

    parser = _parser(path)
    assert parser.has_section("existing")
    assert parser.get("existing", "Description") == "Keep me"
    order = parser.get("General", "Order").split(",")
    assert order[0] == RULE_PREFIX + "games"
    assert "existing" in order
    assert parser.get(RULE_PREFIX + "brave", "opacityactive") == "92"
    assert parser.get(RULE_PREFIX + "brave", "opacityinactive") == "86"
    assert result.groups
    assert result.backup is not None


def test_apply_is_idempotent_and_keeps_one_rule_per_app(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    apply_rules(path, runner=lambda *args, **kwargs: None)
    apply_rules(path, runner=lambda *args, **kwargs: None)
    parser = _parser(path)
    groups = [group for group in parser.sections() if group.startswith(RULE_PREFIX)]
    assert len(groups) == 15
    assert len(set(groups)) == len(groups)
    order = parser.get("General", "Order").split(",")
    assert len(order) == len(set(order))


def test_dry_run_does_not_write_or_backup(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    path.write_text("[General]\nOrder=existing\n", encoding="utf-8")
    before = path.read_bytes()
    result = apply_rules(path, dry_run=True)
    assert result.groups
    assert path.read_bytes() == before
    assert result.backup is None


def test_remove_only_removes_rice_rules(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    path.write_text(
        "[General]\nOrder=existing\n\n[existing]\nDescription=Keep me\n",
        encoding="utf-8",
    )
    apply_rules(path, runner=lambda *args, **kwargs: None)
    result = remove_rules(path)
    parser = _parser(path)
    assert parser.has_section("existing")
    assert not any(
        group.startswith(RULE_PREFIX)
        for group in parser.sections()
    )
    assert result.groups


def test_status_reports_rules(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    apply_rules(path, runner=lambda *args, **kwargs: None)
    state = status(path)
    assert state["enabled"] is True
    assert state["count"] == 15
    assert RULE_PREFIX + "games" in state["groups"]


def test_no_generated_rule_forces_fullscreen():
    from rice.appearance import _rule_groups

    for _group, values in _rule_groups():
        assert "fullscreen" not in values
        assert "fullscreenrule" not in values
