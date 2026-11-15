import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web"

TABS = ("Apps", "Outputs", "Layout", "Placement", "Startup", "Autostart", "Widgets", "Theme", "Apply")


def test_ui_contains_all_tabs():
    text = (WEB / "index.html").read_text(encoding="utf-8")
    for tab in TABS:
        assert f">{tab}<" in text


def test_ui_has_canvas_and_auth_client():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "pointerdown" in js
    assert "Authorization" not in js or "sessionStorage" in js
    assert "getContext" in js or "canvas" in js


def test_ui_has_shell_structure_and_action_buttons():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for marker in ("<nav", "<main", "<footer", 'src="app.js"', 'href="style.css"'):
        assert marker in html
    for button in ("validate", "save", "apply", "status"):
        assert f'id="{button}"' in html


def test_ui_has_no_external_assets():
    for name in ("index.html", "style.css", "app.js"):
        text = (WEB / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), f"external reference in {name}"
        assert "cdn." not in text, f"CDN reference in {name}"
        assert "@import" not in text, f"remote import in {name}"


def test_token_is_read_from_query_and_stored_in_session():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'new URLSearchParams(location.search).get("token")' in js
    assert "sessionStorage.setItem" in js
    assert "sessionStorage.getItem" in js
    assert not re.search(r"token\s*=\s*[\"'][A-Za-z0-9_-]{8,}[\"']", js)
    assert "Bearer" in js


def test_ui_avoids_html_injection_and_eval():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    assert "eval(" not in js
    assert "textContent" in js


def test_css_defines_dark_theme_and_layout_classes():
    css = (WEB / "style.css").read_text(encoding="utf-8")
    for marker in (".canvas", ".zone", "grid-template-columns", "@media", "table-wrap", ".input"):
        assert marker in css
    assert "--bg" in css
    assert "font-family" in css


def test_js_keeps_dirty_guard_and_api_helpers():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for marker in (
        "beforeunload",
        "/api/state",
        "/api/validate",
        "/api/config",
        "/api/apply",
        "state.dirty",
        "Content-Type",
    ):
        assert marker in js


def test_layout_editor_supports_drag_resize_add_and_remove():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for token in ("pointerdown", "pointermove", "pointerup", "resize-zone", "add-zone", "remove-zone"):
        assert token in js


def test_zone_updates_stay_relative():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "Math.min(1" in js
    assert "Math.max(0" in js


def test_layout_renders_a_canvas_per_output_with_zone_helpers():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'for (const output of outputs)' in js
    assert 'make("div", "canvas")' in js
    assert "canvas.dataset.outputId = output.id" in js
    assert "function outputAspect" in js
    assert "16 / 9" in js
    for helper in (
        "function renderLayout",
        "function dragZone",
        "function addZone",
        "function removeZone",
        "function snap",
    ):
        assert helper in js
    assert '"custom-" + index' in js
    assert "kind: \"app\"" in js
    assert "gap_px: 8" in js


def test_structured_tabs_have_editors():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for token in (
        "renderApps",
        "renderPlacement",
        "renderStartup",
        "renderAutostart",
        "renderWidgets",
        "renderTheme",
        "renderOutputs",
    ):
        assert f"function {token}(" in js


def test_apply_warns_before_leaving_dirty_state():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "beforeunload" in js
    assert "state.dirty" in js


def test_editors_mutate_local_state_only():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for token in (
        "state.config.app",
        "state.config.placement",
        "state.config.startup",
        "state.config.autostart",
        "state.config.desktop_widget",
        "state.config.theme",
        "markDirty",
    ):
        assert token in js
    # Editing a field must not go through the network; only Save and Apply do.
    edit_helper = js.split("function textField(")[1].split("function selectField(")[0]
    assert "api(" not in edit_helper
    assert "fetch(" not in edit_helper


def test_outputs_editor_offers_roles_and_reads_connectors_from_config():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for role in ('"main"', '"side"', '"portrait"', '"custom"'):
        assert role in js
    assert "ROLE_CHOICES" in js
    # Connectors are detected at runtime; the UI must not ship a fixed list.
    for connector in ("DP-1", "HDMI-A-1", "eDP-1", "DP-2"):
        assert connector not in js
    assert "state.config.output" in js


def test_theme_outputs_are_built_from_configured_outputs():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "themeOutputOptions" in js
    assert "state.outputs" in js
    assert "selectedOptions" in js


def test_apply_posts_config_before_apply():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    body = js.split("async function applyDocument(")[1].split("\nasync function ")[0]
    assert body.index("/api/config") < body.index("/api/apply")
