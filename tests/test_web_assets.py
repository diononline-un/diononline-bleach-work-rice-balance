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
    for marker in (".canvas", ".zone", "grid-template-columns", "@media", "json-editor"):
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
