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
    monkeypatch.setattr(web_ui, "DELIVERABLES_DIR", str(tmp_path / "deliverables"))
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


def test_cross_origin_get_rejected_and_no_cors_header(auth_server):
    # Read endpoints are gated like the state-changing ones: a cross-origin
    # page gets neither the data nor a CORS header that would let it read.
    host, port = auth_server
    status, headers = _get(port, origin="https://evil.example")
    assert status == 401
    assert "access-control-allow-origin" not in {k.lower() for k in headers}


def test_same_origin_get_echoes_origin(auth_server):
    host, port = auth_server
    status, headers = _get(port, origin=f"http://127.0.0.1:{port}")
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == f"http://127.0.0.1:{port}"


# --- read-endpoint gating (PR: fix/web-ui-read-auth) -----------------------

TUNNEL_HEADERS = {"Host": "tunnel.example.com"}


def _read(port, path="/api/config", headers=None, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, headers=dict(headers or {}))
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw[:60]
        return resp.status, data
    finally:
        conn.close()


def test_tunnel_read_config_without_token_rejected(auth_server):
    status, _ = _read(auth_server[1], headers=TUNNEL_HEADERS)
    assert status == 401


def test_cross_origin_page_read_rejected(auth_server):
    status, _ = _read(auth_server[1], headers={**TUNNEL_HEADERS, "Origin": "http://evil.example"})
    assert status == 401


def test_all_read_endpoints_gated_without_token(auth_server):
    for path in ("/api/status", "/api/logs", "/api/deliverables",
                 "/api/classify?topic=nature", "/api/create/status"):
        status, _ = _read(auth_server[1], path=path, headers=TUNNEL_HEADERS)
        assert status == 401, path


def test_tunnel_read_with_header_token_allowed(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", "sekrit")
    status, _ = _read(auth_server[1], headers={**TUNNEL_HEADERS, "X-Shorts-Token": "sekrit"})
    assert status == 200


def test_tunnel_read_with_bearer_token_allowed(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", "sekrit")
    status, _ = _read(auth_server[1], headers={**TUNNEL_HEADERS, "Authorization": "Bearer sekrit"})
    assert status == 200


def test_same_origin_browser_read_allowed(auth_server):
    # The dashboard's own fetch()/video requests send no Origin header but
    # announce same-origin via Sec-Fetch-Site; this is the phone-on-Wi-Fi case.
    status, _ = _read(auth_server[1], headers={**TUNNEL_HEADERS, "Sec-Fetch-Site": "same-origin"})
    assert status == 200


def test_direct_navigation_to_read_needs_token(auth_server):
    # A browser navigating straight to an API URL sends Sec-Fetch-Site: none:
    # without the page context it is just a stranger with the URL.
    status, _ = _read(auth_server[1], headers={**TUNNEL_HEADERS, "Sec-Fetch-Site": "none"})
    assert status == 401


def test_local_read_still_allowed(auth_server):
    status, _ = _read(auth_server[1], headers={"Host": "127.0.0.1"})
    assert status == 200


def _probe_media():
    os.makedirs(web_ui.DELIVERABLES_DIR, exist_ok=True)
    probe = os.path.join(web_ui.DELIVERABLES_DIR, "short_probe.mp4")
    with open(probe, "wb") as f:
        f.write(b"\x00" * 64)
    return probe


def test_media_without_token_rejected(auth_server):
    _probe_media()
    status, _ = _read(auth_server[1], "/deliverables/short_probe.mp4", headers=TUNNEL_HEADERS)
    assert status == 401


def test_media_with_token_allowed(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", "sekrit")
    _probe_media()
    status, _ = _read(auth_server[1], "/deliverables/short_probe.mp4",
                      headers={**TUNNEL_HEADERS, "X-Shorts-Token": "sekrit"})
    assert status == 200


def test_media_same_origin_allowed(auth_server):
    _probe_media()
    status, _ = _read(auth_server[1], "/deliverables/short_probe.mp4",
                      headers={**TUNNEL_HEADERS, "Sec-Fetch-Site": "same-origin"})
    assert status == 200


def test_head_read_gated_too(auth_server):
    status, _ = _read(auth_server[1], "/api/status", headers=TUNNEL_HEADERS, method="HEAD")
    assert status == 401


def test_dashboard_page_stays_public(auth_server, tmp_path, monkeypatch):
    webdir = tmp_path / "web"
    webdir.mkdir()
    (webdir / "index.html").write_text("<html>probe</html>")
    monkeypatch.setattr(web_ui, "WEB_DIR", str(webdir))
    status, _ = _read(auth_server[1], "/")
    assert status == 200


def test_logs_lines_param_invalid_falls_back(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", "sekrit")
    status, data = _read(auth_server[1], "/api/logs?lines=banana",
                         headers={**TUNNEL_HEADERS, "X-Shorts-Token": "sekrit"})
    assert status == 200
    assert "lines" in data


def test_logs_lines_param_clamped(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", "sekrit")
    status, data = _read(auth_server[1], "/api/logs?lines=999999",
                         headers={**TUNNEL_HEADERS, "X-Shorts-Token": "sekrit"})
    assert status == 200
    assert len(data["lines"]) <= 500
