import configparser
from pathlib import Path

from rice.appearance import RULE_PREFIX, apply_rules, remove_rules, status


def _rules(path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(path.parent / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(path.parent / "state"))
    return path


def _parser(path: Path):
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def _legacy_rules():
    return (
        "[General]\nOrder=existing,rice-appearance-code\n\n"
        "[existing]\nDescription=Keep me\ntypes=1\n\n"
        "[rice-appearance-code]\nDescription=Old rice rule\nopacityactive=92\n"
    )


def test_apply_removes_legacy_rules_and_preserves_existing(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    path.write_text(_legacy_rules(), encoding="utf-8")
    result = apply_rules(path, runner=lambda *args, **kwargs: None)

    parser = _parser(path)
    assert parser.has_section("existing")
    assert parser.get("existing", "Description") == "Keep me"
    assert not any(group.startswith(RULE_PREFIX) for group in parser.sections())
    assert parser.get("General", "Order") == "existing"
    assert result.groups == ()
    assert result.backup is not None


def test_apply_is_idempotent_with_no_rules(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    apply_rules(path, runner=lambda *args, **kwargs: None)
    apply_rules(path, runner=lambda *args, **kwargs: None)
    parser = _parser(path)
    assert not any(group.startswith(RULE_PREFIX) for group in parser.sections())
    assert parser.get("General", "Order") == ""


def test_dry_run_does_not_write_or_backup(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    path.write_text(_legacy_rules(), encoding="utf-8")
    before = path.read_bytes()
    result = apply_rules(path, dry_run=True)
    assert result.groups == ()
    assert path.read_bytes() == before
    assert result.backup is None


def test_remove_only_removes_rice_rules(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    path.write_text(_legacy_rules(), encoding="utf-8")
    result = remove_rules(path)
    parser = _parser(path)
    assert parser.has_section("existing")
    assert not any(group.startswith(RULE_PREFIX) for group in parser.sections())
    assert result.groups == (RULE_PREFIX + "code",)


def test_status_reports_no_rules(tmp_path, monkeypatch):
    path = _rules(tmp_path / "kwinrulesrc", monkeypatch)
    state = status(path)
    assert state["enabled"] is False
    assert state["count"] == 0
    assert state["groups"] == []
