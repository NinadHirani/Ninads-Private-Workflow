"""Web UI access control: every non-local request needs a real credential.

scripts/web_ui.py serves the maker dashboard on 0.0.0.0 and is published
through a fixed public tunnel address. Earlier revisions trusted browser
fetch metadata (an Origin header matching the Host, or
Sec-Fetch-Site: same-origin) as authorization. Both are trivially forged
by any raw HTTP client, which once granted a tunnel caller full read
access to config, logs, and deliverable media. These tests pin the real
model:

- the machine itself (loopback client address AND loopback Host) needs no
  credential;
- every other caller needs the token from SHORTS_UI_TOKEN in .env (as the
  X-Shorts-Token header or 'Authorization: Bearer'), or an HttpOnly
  session cookie minted by POST /api/session in exchange for that token;
- forged Origin / Sec-Fetch-Site / Host headers are never accepted as
  authorization, on reads or on state-changing POSTs;
- CORS preflight answers openly (it grants nothing; the real request is
  still authenticated) so the Vercel app can send its token;
- static assets stay public; the token never appears in responses.
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

TUNNEL_HOST = "tunnel.example.com"
TOKEN = "t0ken-123"


@pytest.fixture(scope="module")
def auth_server():
    yield from _start_server("127.0.0.1")


@pytest.fixture(scope="module")
def public_server():
    yield from _start_server("0.0.0.0")


def _start_server(bind_host):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_host, 0))
    port = s.getsockname()[1]
    s.close()

    os.makedirs(web_ui.WEB_DIR, exist_ok=True)
    server = web_ui.ThreadingHTTPServer((bind_host, port), web_ui.DashboardHandler)
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


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return None


def _request(port, method, path, headers=None, body=None, host_ip="127.0.0.1"):
    headers = dict(headers or {})
    conn = http.client.HTTPConnection(host_ip, port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw[:120]
        return resp.status, data, dict(resp.getheaders())
    finally:
        conn.close()


def _read(port, path="/api/config", headers=None, method="GET", host_ip="127.0.0.1"):
    return _request(port, method, path, headers=headers, host_ip=host_ip)


def _post_json(port, path, headers=None, payload=None, host_ip="127.0.0.1"):
    body = json.dumps(payload if payload is not None else {"probe_key": "probe_val"})
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    return _request(port, "POST", path, headers=headers, body=body, host_ip=host_ip)


def _login(port, token=TOKEN, headers=None):
    status, data, resp_headers = _post_json(
        port, "/api/session", headers=headers, payload={"token": token})
    cookie = ""
    for key, value in resp_headers.items():
        if key.lower() == "set-cookie":
            cookie = value.split(";", 1)[0]
    return status, data, cookie, resp_headers


def _tunnel(**extra):
    headers = {"Host": TUNNEL_HOST}
    headers.update(extra)
    return headers


def _probe_media():
    os.makedirs(web_ui.DELIVERABLES_DIR, exist_ok=True)
    probe = os.path.join(web_ui.DELIVERABLES_DIR, "short_probe.mp4")
    with open(probe, "wb") as f:
        f.write(b"\x00" * 64)
    return probe


# --- local machine: unchanged, no credential -------------------------------

def test_local_post_config_allowed(auth_server):
    host, port = auth_server
    status, data, _ = _post_json(port, "/api/config", headers={"Host": "127.0.0.1"})
    assert status == 200 and data["status"] == "SUCCESS"


def test_local_read_still_allowed(auth_server):
    host, port = auth_server
    status, _, _ = _read(port, headers={"Host": "127.0.0.1"})
    assert status == 200


# --- forged fetch metadata is never authorization (reads) ------------------

def test_forged_origin_matching_host_read_rejected(auth_server):
    host, port = auth_server
    for path in ("/api/config", "/api/status", "/api/logs?lines=5", "/api/deliverables"):
        status, _, _ = _read(port, path, headers=_tunnel(Origin=f"https://{TUNNEL_HOST}"))
        assert status == 401, path


def test_forged_sec_fetch_site_read_rejected(auth_server):
    host, port = auth_server
    status, _, _ = _read(port, headers=_tunnel(**{"Sec-Fetch-Site": "same-origin"}))
    assert status == 401


def test_forged_origin_and_sec_fetch_together_read_rejected(auth_server):
    host, port = auth_server
    headers = _tunnel(Origin=f"https://{TUNNEL_HOST}", **{"Sec-Fetch-Site": "same-origin"})
    status, _, _ = _read(port, headers=headers)
    assert status == 401


def test_forged_origin_media_rejected(auth_server):
    host, port = auth_server
    _probe_media()
    status, _, _ = _read(port, "/deliverables/short_probe.mp4",
                         headers=_tunnel(Origin=f"https://{TUNNEL_HOST}"))
    assert status == 401


# --- forged fetch metadata is never authorization (state changes) ----------

def test_forged_origin_post_rejected(auth_server):
    host, port = auth_server
    status, _, _ = _post_json(port, "/api/config", headers=_tunnel(Origin=f"https://{TUNNEL_HOST}"))
    assert status == 401


def test_forged_sec_fetch_post_rejected(auth_server):
    host, port = auth_server
    status, _, _ = _post_json(port, "/api/maker/start",
                              headers=_tunnel(**{"Sec-Fetch-Site": "same-origin"}))
    assert status == 401


def test_forged_origin_maker_start_rejected(auth_server):
    host, port = auth_server
    status, _, _ = _post_json(port, "/api/maker/start", headers=_tunnel(Origin=f"https://{TUNNEL_HOST}"))
    assert status == 401


def test_cross_origin_post_without_token_rejected(auth_server):
    host, port = auth_server
    status, data, _ = _post_json(port, "/api/config",
                                 headers=_tunnel(Origin="https://evil.example"))
    assert status == 401


def test_cross_origin_read_rejected_and_no_cors_header(auth_server):
    host, port = auth_server
    status, _, headers = _read(port, headers=_tunnel(Origin="https://evil.example"))
    assert status == 401
    assert "access-control-allow-origin" not in {k.lower() for k in headers}


def test_local_drive_by_with_wrong_origin_rejected(auth_server):
    """A webpage open anywhere drive-by-POSTing to localhost carries its own
    Origin; the mismatch blocks it even though the caller is the machine."""
    host, port = auth_server
    status, _, _ = _post_json(port, "/api/maker/start",
                              headers={"Host": "127.0.0.1", "Origin": "https://evil.example"})
    assert status == 401


# --- forged Host cannot fake the local machine ------------------------------

def test_forged_localhost_host_from_lan_rejected(public_server):
    lan_ip = _lan_ip()
    if not lan_ip:
        pytest.skip("no non-loopback interface available")
    host, port = public_server
    status, _, _ = _read(port, headers={"Host": "localhost"}, host_ip=lan_ip)
    assert status == 401
    status, _, _ = _post_json(port, "/api/maker/start", headers={"Host": "localhost"}, host_ip=lan_ip)
    assert status == 401
    # a forged matching Origin is no better from outside
    status, _, _ = _read(port, headers={"Host": "localhost", "Origin": "http://localhost:8088"},
                         host_ip=lan_ip)
    assert status == 401


def test_lan_caller_with_token_allowed(public_server):
    lan_ip = _lan_ip()
    if not lan_ip:
        pytest.skip("no non-loopback interface available")
    host, port = public_server
    import os as _os
    _os.environ["SHORTS_UI_TOKEN"] = TOKEN
    try:
        status, _, _ = _read(port, headers={"Host": lan_ip, "X-Shorts-Token": TOKEN}, host_ip=lan_ip)
        assert status == 200
    finally:
        _os.environ.pop("SHORTS_UI_TOKEN", None)


# --- token header path ------------------------------------------------------

def test_tunnel_read_with_header_token_allowed(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, _, _ = _read(auth_server[1], headers=_tunnel(**{"X-Shorts-Token": TOKEN}))
    assert status == 200


def test_tunnel_read_with_bearer_token_allowed(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, _, _ = _read(auth_server[1], headers=_tunnel(**{"Authorization": f"Bearer {TOKEN}"}))
    assert status == 200


def test_tunnel_post_with_header_token_allowed(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, data, _ = _post_json(auth_server[1], "/api/config", headers=_tunnel(**{"X-Shorts-Token": TOKEN}))
    assert status == 200 and data["status"] == "SUCCESS"


def test_wrong_token_rejected(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, _, _ = _read(auth_server[1], headers=_tunnel(**{"X-Shorts-Token": "wrong"}))
    assert status == 401


def test_all_read_endpoints_gated_without_token(auth_server):
    for path in ("/api/status", "/api/logs", "/api/deliverables",
                 "/api/classify?topic=nature", "/api/create/status", "/api/queue"):
        status, _, _ = _read(auth_server[1], path=path, headers=_tunnel())
        assert status == 401, path


def test_head_read_gated_too(auth_server):
    status, _, _ = _read(auth_server[1], "/api/status", headers=_tunnel(), method="HEAD")
    assert status == 401


# --- session login flow ------------------------------------------------------

def test_login_wrong_token_rejected_and_no_cookie(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, _, cookie, _ = _login(auth_server[1], token="wrong")
    assert status == 401
    assert cookie == ""


def test_login_without_token_configured_fails_closed(auth_server):
    status, _, _, _ = _login(auth_server[1], token="whatever")
    assert status == 401


def test_login_sets_httponly_strict_cookie_and_never_echoes_token(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    status, data, cookie, resp_headers = _login(port)
    assert status == 200
    assert cookie.startswith(f"{web_ui.SESSION_COOKIE}=")
    assert cookie.split("=", 1)[1] != TOKEN
    set_cookie = next(v for k, v in resp_headers.items() if k.lower() == "set-cookie")
    assert "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie and "Path=/" in set_cookie
    assert "Secure" not in set_cookie  # plain HTTP login stays playable on the LAN
    assert TOKEN not in json.dumps(data)
    assert TOKEN not in set_cookie


def test_login_over_https_marks_cookie_secure(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    _, _, _, resp_headers = _login(auth_server[1], headers={"X-Forwarded-Proto": "https"})
    set_cookie = next(v for k, v in resp_headers.items() if k.lower() == "set-cookie")
    assert "Secure" in set_cookie


def test_session_cookie_grants_reads_and_media(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    _, _, cookie, _ = _login(port)
    assert cookie
    for path in ("/api/config", "/api/status", "/api/logs?lines=5", "/api/queue"):
        status, _, _ = _read(port, path, headers=_tunnel(**{"Cookie": cookie}))
        assert status == 200, path
    _probe_media()
    status, _, _ = _read(port, "/deliverables/short_probe.mp4", headers=_tunnel(**{"Cookie": cookie}))
    assert status == 200


def test_session_cookie_grants_state_changes(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    _, _, cookie, _ = _login(port)
    status, data, _ = _post_json(port, "/api/config", headers=_tunnel(**{"Cookie": cookie}))
    assert status == 200 and data["status"] == "SUCCESS"


def test_forged_session_cookie_rejected(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, _, _ = _read(auth_server[1], headers=_tunnel(**{"Cookie": f"{web_ui.SESSION_COOKIE}=forged"}))
    assert status == 401


def test_logout_revokes_the_session(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    _, _, cookie, _ = _login(port)
    status, _, _ = _request(port, "DELETE", "/api/session", headers=_tunnel(**{"Cookie": cookie}))
    assert status == 200
    status, _, _ = _read(port, headers=_tunnel(**{"Cookie": cookie}))
    assert status == 401


# --- CORS preflight supports the token header but grants nothing ------------

def test_vercel_preflight_allows_token_request_then_real_call_authenticates(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    host, port = auth_server
    preflight_headers = {
        "Host": TUNNEL_HOST,
        "Origin": "https://shorts-factory-olive.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-shorts-token",
    }
    status, _, headers = _request(port, "OPTIONS", "/api/maker/start", headers=preflight_headers)
    assert status == 200
    lower = {k.lower(): v for k, v in headers.items()}
    assert lower.get("access-control-allow-origin") == "https://shorts-factory-olive.vercel.app"
    assert "x-shorts-token" in lower.get("access-control-allow-headers", "").lower()
    # the actual call still has to prove itself (config save: safe, no daemon)
    status, _, _ = _post_json(port, "/api/config", headers=_tunnel())
    assert status == 401
    status, data, _ = _post_json(port, "/api/config", headers=_tunnel(**{"X-Shorts-Token": TOKEN}))
    assert status == 200 and data["status"] == "SUCCESS"


def test_preflight_itself_returns_no_data(auth_server):
    host, port = auth_server
    status, _, _ = _request(port, "OPTIONS", "/api/config",
                            headers={"Origin": "https://shorts-factory-olive.vercel.app",
                                     "Access-Control-Request-Method": "GET"})
    assert status == 200


# --- public assets and diagnostics ------------------------------------------

def test_dashboard_page_stays_public(auth_server, tmp_path, monkeypatch):
    webdir = tmp_path / "web"
    webdir.mkdir()
    (webdir / "index.html").write_text("<html>probe</html>")
    monkeypatch.setattr(web_ui, "WEB_DIR", str(webdir))
    status, _, _ = _read(auth_server[1], "/")
    assert status == 200


def test_logs_lines_param_invalid_falls_back(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, data = _read(auth_server[1], "/api/logs?lines=banana",
                         headers=_tunnel(**{"X-Shorts-Token": TOKEN}))[:2]
    assert status == 200
    assert "lines" in data


def test_logs_lines_param_clamped(auth_server, monkeypatch):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    status, data = _read(auth_server[1], "/api/logs?lines=999999",
                         headers=_tunnel(**{"X-Shorts-Token": TOKEN}))[:2]
    assert status == 200
    assert len(data["lines"]) <= 500


def test_queue_endpoint_is_read_only_view(auth_server, monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTS_UI_TOKEN", TOKEN)
    import scripts.uploader as uploader
    monkeypatch.setattr(uploader, "QUEUE_FILE", str(tmp_path / "dual_queue.json"))
    with open(tmp_path / "dual_queue.json", "w") as f:
        json.dump([{"video": "edited/short_x.mp4", "reason": "YouTube daily quota reached"}], f)
    status, data = _read(auth_server[1], "/api/queue", headers=_tunnel(**{"X-Shorts-Token": TOKEN}))[:2]
    assert status == 200
    assert data["queue"][0]["video"] == "edited/short_x.mp4"
