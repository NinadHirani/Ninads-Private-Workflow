"""Web UI access control: state-changing endpoints require auth off-machine.

scripts/web_ui.py serves the maker dashboard on 0.0.0.0 and is published
through a fixed public tunnel address. State-changing endpoints (create,
maker start/stop, config save) used to accept any caller, so a webpage open
in any browser (cross-origin drive-by) or anyone with the tunnel URL could
drive real uploads. These tests pin the gate:

- same-origin calls (the dashboard itself, desktop or phone on Wi-Fi) keep
  working with no token;
- cross-origin pages and non-local non-browser callers are rejected unless
  they send the token from SHORTS_UI_TOKEN in .env (fail closed);
- cross-origin pages never get an Access-Control-Allow-Origin header, so
  they cannot read responses either.
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


@pytest.fixture(scope="module")
def auth_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    os.makedirs(web_ui.WEB_DIR, exist_ok=True)
    server = web_ui.ThreadingHTTPServer(("127.0.0.1", port), web_ui.DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield "127.0.0.1", port
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(web_ui, "CONTEXT_FILE", str(tmp_path / "context.json"))
    monkeypatch.setattr(web_ui, "STATE_FILE", str(tmp_path / "auto_state.json"))
    monkeypatch.setattr(shortsctl, "STATE_FILE", str(tmp_path / "auto_state.json"))
    monkeypatch.delenv("SHORTS_UI_TOKEN", raising=False)


def _post(host_header, port, path="/api/config", origin=None, token=None,
          token_header="X-Shorts-Token"):
    headers = {"Content-Type": "application/json"}
    if host_header:
        headers["Host"] = host_header
    if origin:
        headers["Origin"] = origin
    if token:
        if token_header == "Authorization":
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers[token_header] = token
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", path, body=json.dumps({"probe_key": "probe_val"}), headers=headers)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read().decode()), dict(resp.getheaders())
    finally:
        conn.close()


def _get(port, path="/api/status", origin=None):
    headers = {}
    if origin:
        headers["Origin"] = origin
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        resp.read()
        return resp.status, dict(resp.getheaders())
    finally:
        conn.close()


def test_local_post_config_allowed(auth_server):
    host, port = auth_server
    status, data, _ = _post(None, port)
    assert status == 200 and data["status"] == "SUCCESS"


def test_same_origin_post_allowed(auth_server):
    host, port = auth_server
    status, data, _ = _post(None, port, origin=f"http://127.0.0.1:{port}")
    assert status == 200 and data["status"] == "SUCCESS"


def test_cross_origin_post_without_token_rejected(auth_server):
    host, port = auth_server
    status, data, _ = _post(None, port, origin="https://evil.example")
    assert status == 401
    assert "SHORTS_UI_TOKEN" in data["error"]


def test_cross_origin_post_with_header_token_allowed(auth_server, monkeypatch):
    host, port = auth_server
    monkeypatch.setenv("SHORTS_UI_TOKEN", "t0ken-123")
    status, data, _ = _post(None, port, origin="https://app.example", token="t0ken-123")
    assert status == 200 and data["status"] == "SUCCESS"


def test_cross_origin_post_with_bearer_token_allowed(auth_server, monkeypatch):
    host, port = auth_server
    monkeypatch.setenv("SHORTS_UI_TOKEN", "t0ken-123")
    status, data, _ = _post(None, port, origin="https://app.example",
                            token="t0ken-123", token_header="Authorization")
    assert status == 200 and data["status"] == "SUCCESS"


def test_wrong_token_rejected(auth_server, monkeypatch):
    host, port = auth_server
    monkeypatch.setenv("SHORTS_UI_TOKEN", "t0ken-123")
    status, data, _ = _post(None, port, origin="https://app.example", token="wrong")
    assert status == 401


def test_tunnel_host_post_without_token_rejected(auth_server):
    host, port = auth_server
    status, data, _ = _post("ninad-shorts.loca.lt", port)
    assert status == 401
    assert "SHORTS_UI_TOKEN" in data["error"]


def test_tunnel_host_post_with_token_allowed(auth_server, monkeypatch):
    host, port = auth_server
    monkeypatch.setenv("SHORTS_UI_TOKEN", "t0ken-123")
    status, data, _ = _post("ninad-shorts.loca.lt", port, token="t0ken-123")
    assert status == 200 and data["status"] == "SUCCESS"


def test_maker_start_gated_too(auth_server, monkeypatch):
    host, port = auth_server
    monkeypatch.setenv("SHORTS_UI_TOKEN", "t0ken-123")
    status, data, _ = _post(None, port, path="/api/maker/start", origin="https://evil.example")
    assert status == 401


def test_cross_origin_get_has_no_cors_header(auth_server):
    host, port = auth_server
    status, headers = _get(port, origin="https://evil.example")
    assert status == 200
    assert "access-control-allow-origin" not in {k.lower() for k in headers}


def test_same_origin_get_echoes_origin(auth_server):
    host, port = auth_server
    status, headers = _get(port, origin=f"http://127.0.0.1:{port}")
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == f"http://127.0.0.1:{port}"
