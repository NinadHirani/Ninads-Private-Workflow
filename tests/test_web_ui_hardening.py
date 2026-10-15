"""Web UI hardening: login rate limiting, Secure-cookie scoping, and clean
404s on deliverable paths that name a directory.

- POST /api/session wrong-token attempts feed a rolling global limiter
  (per-IP is meaningless here: every remote caller arrives through the one
  local tunnel process). A correct token is never held back, so the owner
  can always log in.
- The session cookie carries Secure when the login came over HTTPS (proxy
  header) or when the Host is public; plain-HTTP LAN and loopback use keeps
  the cookie sendable.
- /deliverables/<name> whose basename is not a regular file (for example
  "/deliverables/..") is a clean 404, not a server error.
"""
import http.client
import json
import os
import socket
import threading
import time

import pytest

import scripts.shortsctl as shortsctl
import scripts.web_ui as web_ui

TOKEN = "hardn-t0ken-7"


@pytest.fixture(scope="module")
def server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    s.close()
    os.makedirs(web_ui.WEB_DIR, exist_ok=True)
    httpd = web_ui.ThreadingHTTPServer(("0.0.0.0", port), web_ui.DashboardHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield "127.0.0.1", port
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(web_ui, "CONTEXT_FILE", str(tmp_path / "context.json"))
    monkeypatch.setattr(web_ui, "STATE_FILE", str(tmp_path / "auto_state.json"))
    monkeypatch.setattr(shortsctl, "STATE_FILE", str(tmp_path / "auto_state.json"))
    monkeypatch.setattr(web_ui, "DELIVERABLES_DIR", str(tmp_path / "deliverables"))
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    monkeypatch.setattr(web_ui, "_SESSIONS", {})
    monkeypatch.setattr(web_ui, "_FAILED_LOGINS", [])


def _request(port, method, path, headers=None, body=None, host_ip="127.0.0.1"):
    conn = http.client.HTTPConnection(host_ip, port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=dict(headers or {}))
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw[:120]
        return resp.status, data, dict(resp.getheaders())
    finally:
        conn.close()


def _post_json(port, path, payload, headers=None):
    body = json.dumps(payload)
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    return _request(port, "POST", path, headers=headers, body=body)


def _login(port, token=TOKEN, headers=None):
    return _post_json(port, "/api/session", {"token": token}, headers=headers)


def _set_cookie(headers):
    return next((v for k, v in headers.items() if k.lower() == "set-cookie"), "")


def _retry_after(headers):
    return next((k for k in headers if k.lower() == "retry-after"), None)


def test_wrong_tokens_401_until_limit_then_429(server, monkeypatch):
    monkeypatch.setattr(web_ui, "SESSION_FAIL_LIMIT", 3)
    monkeypatch.setattr(web_ui, "SESSION_FAIL_WINDOW_SECONDS", 900)
    host, port = server
    for _ in range(3):
        status, _, _ = _login(port, token="wrong")
        assert status == 401
    status, _, headers = _login(port, token="wrong")
    assert status == 429
    assert _retry_after(headers) is not None


def test_correct_token_still_logs_in_after_limit(server, monkeypatch):
    monkeypatch.setattr(web_ui, "SESSION_FAIL_LIMIT", 2)
    monkeypatch.setattr(web_ui, "SESSION_FAIL_WINDOW_SECONDS", 900)
    host, port = server
    for _ in range(4):
        _login(port, token="wrong")
    status, _, headers = _login(port)
    assert status == 200
    assert _set_cookie(headers).startswith(f"{web_ui.SESSION_COOKIE}=")
    # a successful login clears the limiter: wrong tokens are 401 again
    status, _, _ = _login(port, token="wrong")
    assert status == 401


def test_rate_limit_window_expires(server, monkeypatch):
    monkeypatch.setattr(web_ui, "SESSION_FAIL_LIMIT", 1)
    monkeypatch.setattr(web_ui, "SESSION_FAIL_WINDOW_SECONDS", 5)
    host, port = server
    assert _login(port, token="wrong")[0] == 401
    assert _login(port, token="wrong")[0] == 429
    now = time.time()
    monkeypatch.setattr(web_ui, "_FAILED_LOGINS", [now - 10, now - 10])
    assert _login(port, token="wrong")[0] == 401


def test_public_host_gets_secure_cookie(server):
    host, port = server
    status, _, headers = _login(port, headers={"Host": "tunnel.example.com"})
    assert status == 200
    assert "Secure" in _set_cookie(headers)


def test_lan_host_cookie_stays_plain(server):
    host, port = server
    status, _, headers = _login(port, headers={"Host": "10.1.2.3:8088"})
    assert status == 200
    assert "Secure" not in _set_cookie(headers)


def test_loopback_cookie_stays_plain(server):
    host, port = server
    status, _, headers = _login(port, headers={"Host": "127.0.0.1"})
    assert status == 200
    assert "Secure" not in _set_cookie(headers)


def test_deliverables_directory_path_is_clean_404_and_server_survives(server):
    host, port = server
    os.makedirs(web_ui.DELIVERABLES_DIR, exist_ok=True)
    for path in ("/deliverables/..", "/deliverables/missing.mp4"):
        status, _, _ = _request(port, "GET", path, headers={"Host": "127.0.0.1"})
        assert status == 404, path
    # the server thread survived and still serves authorized reads
    status, _, _ = _request(port, "GET", "/api/status", headers={"Host": "127.0.0.1"})
    assert status == 200


def test_deliverables_real_file_still_served(server):
    host, port = server
    os.makedirs(web_ui.DELIVERABLES_DIR, exist_ok=True)
    with open(os.path.join(web_ui.DELIVERABLES_DIR, "short_x.mp4"), "wb") as f:
        f.write(b"\x00" * 64)
    status, _, headers = _request(port, "GET", "/deliverables/short_x.mp4",
                                  headers={"Host": "127.0.0.1"})
    assert status == 200
