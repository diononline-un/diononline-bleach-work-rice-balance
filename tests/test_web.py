import http.client
import json
import threading
from pathlib import Path

import pytest

from rice.config import load_config, save_config
from rice.web import make_server

TOKEN = "test-token"

DEFAULTS = Path(__file__).resolve().parents[1] / "defaults" / "rice.toml"


@pytest.fixture()
def server(tmp_path):
    path = tmp_path / "rice.toml"
    save_config(path, load_config(DEFAULTS))
    httpd = make_server(path, TOKEN, apply_func=lambda *a, **k: None)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, path
    httpd.shutdown()
    httpd.server_close()


def request(httpd, method, path, body=None, token=TOKEN):
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    payload = None if body is None else json.dumps(body)
    conn.request(method, path, body=payload, headers=headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def test_health(server):
    status, body = request(server[0], "GET", "/api/health", token=None)
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_mutations_require_bearer(server):
    status, _ = request(server[0], "PUT", "/api/config", {"config": {}}, token=None)
    assert status == 401


def test_state_contains_config_and_validation(server):
    status, body = request(server[0], "GET", "/api/state")
    state = json.loads(body)
    assert status == 200
    assert "config" in state
    assert "validation" in state
    assert state["validation"] == []


def test_put_config_validates_and_writes(server):
    httpd, path = server
    config = load_config(path)
    config["meta"]["profile_name"] = "edited"
    status, body = request(httpd, "PUT", "/api/config", {"config": config})
    assert status == 200
    assert load_config(path)["meta"]["profile_name"] == "edited"


def test_put_config_rejects_invalid_document(server):
    httpd, path = server
    before = load_config(path)
    config = load_config(path)
    config["placement"][0]["zone"] = "missing"
    status, body = request(httpd, "PUT", "/api/config", {"config": config})
    assert status == 400
    assert "unknown zone" in body.decode()
    assert load_config(path) == before


def test_apply_uses_injected_apply_func(server):
    httpd, path = server
    calls = []
    httpd.apply_func = lambda config_path, dry_run=False: calls.append((config_path, dry_run))
    status, _ = request(httpd, "POST", "/api/apply", {})
    assert status == 200
    assert calls == [(path, False)]


def test_state_requires_bearer(server):
    status, _ = request(server[0], "GET", "/api/state", token=None)
    assert status == 401


def test_outputs_requires_bearer(server):
    status, _ = request(server[0], "GET", "/api/outputs", token=None)
    assert status == 401


def test_wrong_token_is_rejected(server):
    status, _ = request(server[0], "GET", "/api/state", token="wrong-token")
    assert status == 401


def test_validate_endpoint_returns_errors(server):
    status, body = request(server[0], "POST", "/api/validate", {})
    assert status == 200
    assert json.loads(body)["errors"] == []


def test_apply_rejects_invalid_config_without_calling_func(server):
    httpd, path = server
    calls = []
    httpd.apply_func = lambda config_path, dry_run=False: calls.append(config_path)
    config = load_config(path)
    config["placement"][0]["zone"] = "missing"
    save_config(path, config)
    status, _ = request(httpd, "POST", "/api/apply", {})
    assert status == 400
    assert calls == []


def test_backup_copies_current_config(server, tmp_path):
    httpd, path = server
    httpd.backup_root = tmp_path / "backups"
    status, body = request(httpd, "POST", "/api/backup", {})
    assert status == 200
    backup_path = Path(json.loads(body)["path"])
    assert backup_path.is_file()
    assert load_config(backup_path) == load_config(path)


def test_restore_rejects_path_outside_backup_root(server, tmp_path):
    httpd, path = server
    httpd.backup_root = tmp_path / "backups"
    before = load_config(path)
    status, body = request(httpd, "POST", "/api/restore", {"path": "/etc/passwd"})
    assert status == 400
    assert load_config(path) == before


def test_restore_restores_backed_up_config(server, tmp_path):
    httpd, path = server
    httpd.backup_root = tmp_path / "backups"

    status, body = request(httpd, "POST", "/api/backup", {})
    backup_path = json.loads(body)["path"]

    config = load_config(path)
    config["meta"]["profile_name"] = "changed"
    save_config(path, config)

    status, body = request(httpd, "POST", "/api/restore", {"path": backup_path})
    assert status == 200
    assert load_config(path)["meta"].get("profile_name") is None


def test_static_assets_are_served_without_a_token(server):
    status, body = request(server[0], "GET", "/", token=None)
    assert status == 200
    assert b'id="panel"' in body

    status, body = request(server[0], "GET", "/app.js", token=None)
    assert status == 200
    assert b"/api/state" in body

    status, body = request(server[0], "GET", "/style.css", token=None)
    assert status == 200
    assert b"--bg" in body


def test_static_path_traversal_is_blocked(server):
    status, body = request(server[0], "GET", "/../../etc/passwd", token=None)
    assert status == 404
    status, body = request(server[0], "GET", "/..%2f..%2fetc%2fpasswd", token=None)
    assert status == 404
