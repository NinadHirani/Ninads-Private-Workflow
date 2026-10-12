import os
import json
import time
import socket
import threading
import urllib.request
import pytest

from scripts.web_ui import ThreadingHTTPServer, DashboardHandler, WEB_DIR, DELIVERABLES_DIR


@pytest.fixture(scope="module")
def live_server():
    # Pick an ephemeral free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    os.makedirs(WEB_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.3)
    yield base_url
    server.shutdown()
    server.server_close()


def test_serve_index_html(live_server):
    req = urllib.request.Request(f"{live_server}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type")
        body = resp.read().decode()
        assert "Shorts Factory" in body


def test_api_status(live_server):
    req = urllib.request.Request(f"{live_server}/api/status")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "running" in data
        assert "today_made" in data
        assert "pipeline" in data


def test_api_config_get_and_post(live_server):
    req = urllib.request.Request(f"{live_server}/api/config")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "config" in data

    # Test update
    payload = json.dumps({"test_key": "val123"}).encode("utf-8")
    post_req = urllib.request.Request(f"{live_server}/api/config", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(post_req) as resp:
        assert resp.status == 200
        res_data = json.loads(resp.read().decode())
        assert res_data["status"] == "SUCCESS"
        assert res_data["config"].get("test_key") == "val123"


def test_api_deliverables_and_range_requests(live_server, tmp_path):
    os.makedirs(DELIVERABLES_DIR, exist_ok=True)
    dummy_video = os.path.join(DELIVERABLES_DIR, "test_dummy_stream.mp4")
    with open(dummy_video, "wb") as f:
        f.write(b"0" * 2048)

    try:
        req = urllib.request.Request(f"{live_server}/api/deliverables")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            items = json.loads(resp.read().decode()).get("items", [])
            assert any(item["filename"] == "test_dummy_stream.mp4" for item in items)

        # Test Range request
        range_req = urllib.request.Request(f"{live_server}/deliverables/test_dummy_stream.mp4", headers={"Range": "bytes=0-499"})
        with urllib.request.urlopen(range_req) as resp:
            assert resp.status == 206
            assert resp.headers.get("Content-Range") == "bytes 0-499/2048"
            assert len(resp.read()) == 500
    finally:
        if os.path.exists(dummy_video):
            os.remove(dummy_video)
