"""Frontend/backend auth contract and authenticated media streaming.

Two contracts pinned here:

1. The served dashboard never holds the token: web/index.html must not
   embed SHORTS_UI_TOKEN, must not persist the token in localStorage or
   any other browser storage, must log in once via POST /api/session,
   and must authenticate API calls with the X-Shorts-Token header. The
   static assertions keep a regression (someone re-adding a stored
   token) from ever shipping.
2. Media streaming: deliverable videos stream with Range support, but
   only for a caller with a real credential (session cookie or token
   header). Same proof as every other endpoint.
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

TOKEN = "t0ken-123"
TUNNEL_HOST = "tunnel.example.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    monkeypatch.setattr(web_ui, "_SESSIONS", {})


def _request(port, method, path, headers=None):
    headers = dict(headers or {})
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, body, dict(resp.getheaders())
    finally:
        conn.close()


def _login(port):
    body = json.dumps({"token": TOKEN})
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", "/api/session", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        cookie = ""
        for key, value in resp.getheaders():
            if key.lower() == "set-cookie":
                cookie = value.split(";", 1)[0]
        return resp.status, cookie
    finally:
        conn.close()


def _probe_media():
    os.makedirs(web_ui.DELIVERABLES_DIR, exist_ok=True)
    probe = os.path.join(web_ui.DELIVERABLES_DIR, "short_probe.mp4")
    with open(probe, "wb") as f:
        f.write(b"\x00" * 64)
    return probe


# --- media streaming needs a credential; Range works with the session -------

def test_range_playback_with_session_cookie(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    _probe_media()
    status, cookie = _login(port)
    assert status == 200 and cookie
    status, body, headers = _request(
        port, "GET", "/deliverables/short_probe.mp4",
        headers={"Host": TUNNEL_HOST, "Cookie": cookie, "Range": "bytes=0-15"})
    assert status == 206
    lower = {k.lower(): v for k, v in headers.items()}
    assert lower.get("content-range") == "bytes 0-15/64"
    assert len(body) == 16


def test_range_playback_without_credential_rejected(auth_server):
    host, port = auth_server
    _probe_media()
    status, _, _ = _request(port, "GET", "/deliverables/short_probe.mp4",
                            headers={"Host": TUNNEL_HOST, "Range": "bytes=0-15"})
    assert status == 401


def test_token_header_also_streams_media(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    _probe_media()
    status, body, _ = _request(port, "GET", "/deliverables/short_probe.mp4",
                               headers={"Host": TUNNEL_HOST,
                                        "X-Shorts-Token": TOKEN,
                                        "Range": "bytes=0-15"})
    assert status == 206 and len(body) == 16


# --- frontend contract: the page never holds or stores the token ------------

def _frontend_source():
    with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
        return f.read()


def test_frontend_never_stores_or_embeds_the_token():
    html = _frontend_source()
    assert "SHORTS_UI_TOKEN" not in html           # no env token name in the page
    assert "shorts_factory_api_token" not in html  # no token key in browser storage
    assert "apiTokenInput').value = savedToken()" not in html  # no prefill from storage
    assert "pageToken" in html                     # token kept in page memory only


def test_frontend_logs_in_once_and_authenticates_calls():
    html = _frontend_source()
    assert "'/api/session'" in html                # one-time cookie login
    assert "X-Shorts-Token" in html                # header on every API call
    assert "establishSession" in html
    assert "URL.createObjectURL" in html           # blob playback cross-origin
    assert "Set-Cookie" not in html                # the server sets cookies, not JS
