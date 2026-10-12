#!/usr/bin/env python3
"""
Web UI Server - AI Shorts Factory
Lightweight, zero-dependency mobile dashboard server.
Accessible on local Wi-Fi from iOS Safari or Android Chrome.
Supports HTTP Range requests for smooth video playback.
Includes 1-Click Creative Studio with Remotion & AI visuals.
"""

import os
import re
import sys
import json
import time
import socket
import datetime
import mimetypes
import threading
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import scripts.shortsctl as shortsctl
from scripts.story_pipeline import run_story
from scripts.scene_generator import classify_topic

WEB_DIR = os.path.join(ROOT, "web")
LOG_DIR = os.path.join(ROOT, os.getenv("LOG_PATH", "logs"))
DAEMON_LOG = os.path.join(LOG_DIR, "auto.log")
STATE_FILE = os.path.join(LOG_DIR, "auto_state.json")
CONTEXT_FILE = os.path.join(ROOT, "context.json")
DELIVERABLES_DIR = os.path.join(ROOT, "deliverables")

CREATION_LOCK = threading.Lock()
CREATION_STATE = {
    "active": False,
    "topic": "",
    "step": "idle",
    "status": "idle",
    "detail": "",
    "started_at": 0,
    "result": None,
    "error": None,
}


def get_local_ip() -> str:
    """Best-effort local LAN IP for mobile access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_current_pipeline_stage() -> dict:
    """Analyze the tail of auto.log to determine current stage."""
    if not os.path.exists(DAEMON_LOG):
        return {"stage": "idle", "topic": "", "detail": ""}
    try:
        with open(DAEMON_LOG, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-30:]
        current_topic = ""
        stage = "idle"
        detail = ""
        for line in lines:
            if "Making a Short on" in line:
                m = re.search(r"Making a Short on '([^']+)'", line)
                if m:
                    current_topic = m.group(1)
                stage = "script"
                detail = "Writing AI script"
            elif "Voiceover made with" in line:
                stage = "captions"
                detail = "Generating captions"
            elif "Downloading video from" in line or "Generating AI scene" in line:
                stage = "clips"
                detail = "Generating visuals"
            elif "FFprobe details" in line or "Building story reel" in line or "Remotion" in line:
                stage = "render"
                detail = "Rendering with Remotion"
            elif "Video uploaded successfully" in line:
                stage = "upload_success"
                detail = "Uploaded to YouTube"
            elif "Uploaded" in line and "->" in line:
                stage = "waiting"
                detail = "Waiting for next interval"
        return {"stage": stage, "topic": current_topic, "detail": detail}
    except Exception:
        return {"stage": "idle", "topic": "", "detail": ""}


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep stdout clean; suppress spammy GET polling
        pass

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.serve_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8", head_only=head_only)
        elif path.startswith("/deliverables/"):
            filename = os.path.basename(path)
            file_path = os.path.join(DELIVERABLES_DIR, filename)
            self.serve_media_with_range(file_path, head_only=head_only)
        elif path in ("/manifest.json", "/sw.js", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"):
            rel_path = path.lstrip("/")
            mime = "application/manifest+json" if path.endswith(".json") else (
                "application/javascript" if path.endswith(".js") else "image/png"
            )
            self.serve_file(os.path.join(WEB_DIR, rel_path), mime, head_only=head_only)
        elif path == "/api/status":
            self.handle_api_status()
        elif path == "/api/logs":
            self.handle_api_logs(parsed)
        elif path == "/api/deliverables":
            self.handle_api_deliverables()
        elif path == "/api/config":
            self.handle_api_get_config()
        elif path == "/api/classify":
            self.handle_api_classify(parsed)
        elif path == "/api/create/status":
            self.handle_api_create_status()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        if path == "/api/maker/start":
            self.handle_maker_start(payload)
        elif path == "/api/maker/stop":
            self.handle_maker_stop()
        elif path == "/api/config":
            self.handle_api_set_config(payload)
        elif path == "/api/create":
            self.handle_api_create(payload)
        else:
            self.send_error(404, "Not Found")

    def handle_api_status(self):
        state = shortsctl.load_state()
        runs = state.get("runs", [])
        made = sum(1 for r in runs if r.get("status") in ("SUCCESS", "SUCCESS_LOCAL"))
        today = datetime.date.today().isoformat()
        today_made = sum(1 for r in runs if r.get("status") in ("SUCCESS", "SUCCESS_LOCAL") and r.get("at", "").startswith(today))
        running = shortsctl.daemon_running()
        pid = shortsctl.get_daemon_pid() if running else None
        pipeline = get_current_pipeline_stage() if running else {"stage": "stopped", "topic": "", "detail": "Maker is stopped"}

        self.send_json({
            "running": running,
            "pid": pid,
            "total_made": made,
            "today_made": today_made,
            "started_at": state.get("started_at"),
            "pipeline": pipeline,
            "recent_runs": list(reversed(runs[-10:])),
        })

    def handle_api_logs(self, parsed):
        qs = parse_qs(parsed.query)
        num_lines = int(qs.get("lines", ["60"])[0])
        lines = []
        if os.path.exists(DAEMON_LOG):
            try:
                with open(DAEMON_LOG, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-num_lines:]
            except Exception as e:
                lines = [f"Error reading log: {e}\n"]
        self.send_json({"lines": lines})

    def handle_api_deliverables(self):
        items = []
        if os.path.exists(DELIVERABLES_DIR):
            for fname in os.listdir(DELIVERABLES_DIR):
                if fname.endswith(".mp4"):
                    fpath = os.path.join(DELIVERABLES_DIR, fname)
                    stat = os.stat(fpath)
                    json_path = os.path.join(DELIVERABLES_DIR, fname.rsplit(".", 1)[0] + ".json")
                    meta = {}
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        except Exception:
                            pass
                    items.append({
                        "filename": fname,
                        "url": f"/deliverables/{fname}",
                        "size_bytes": stat.st_size,
                        "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "topic": meta.get("topic") or fname.replace("short_", "").rsplit("_", 1)[0].replace("_", " "),
                        "metadata": meta.get("metadata", {}),
                        "duration": meta.get("duration", 30),
                        "category": meta.get("category", "general"),
                        "style": meta.get("style", "cinematic"),
                        "privacy": meta.get("privacy", "private"),
                    })
        items.sort(key=lambda x: x["created_at"], reverse=True)
        self.send_json({"items": items})

    def handle_api_get_config(self):
        data = {}
        if os.path.exists(CONTEXT_FILE):
            try:
                with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        self.send_json({"config": data})

    def handle_api_set_config(self, payload: dict):
        current = {}
        if os.path.exists(CONTEXT_FILE):
            try:
                with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except Exception:
                pass
        current.update(payload)
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        self.send_json({"status": "SUCCESS", "config": current})

    def handle_api_classify(self, parsed):
        qs = parse_qs(parsed.query)
        topic = qs.get("topic", [""])[0]
        res = classify_topic(topic)
        self.send_json(res)

    def handle_api_create_status(self):
        with CREATION_LOCK:
            self.send_json(dict(CREATION_STATE))

    def handle_api_create(self, payload: dict):
        global CREATION_STATE
        topic = (payload.get("topic") or "").strip()
        if not topic:
            return self.send_json({"status": "FAILED", "error": "Topic cannot be empty"}, 400)

        with CREATION_LOCK:
            if CREATION_STATE["active"]:
                return self.send_json({"status": "FAILED", "error": f"Another short is already generating: '{CREATION_STATE['topic']}'"}, 409)

            duration = int(payload.get("duration") or 45)
            privacy = payload.get("privacy") or "private"
            upload = bool(payload.get("upload", True))

            CREATION_STATE["active"] = True
            CREATION_STATE["topic"] = topic
            CREATION_STATE["step"] = "init"
            CREATION_STATE["status"] = "running"
            CREATION_STATE["detail"] = f"Initializing pipeline for '{topic}'"
            CREATION_STATE["started_at"] = time.time()
            CREATION_STATE["result"] = None
            CREATION_STATE["error"] = None

        def worker():
            global CREATION_STATE
            def on_progress(step, status, detail=None):
                with CREATION_LOCK:
                    CREATION_STATE["step"] = step
                    CREATION_STATE["status"] = status
                    if detail:
                        CREATION_STATE["detail"] = str(detail)

            try:
                result = run_story(
                    topic=topic,
                    duration=duration,
                    privacy=privacy,
                    upload=upload,
                    on_progress=on_progress,
                )
                with CREATION_LOCK:
                    CREATION_STATE["active"] = False
                    CREATION_STATE["status"] = "done" if result.get("status") == "SUCCESS" else "failed"
                    CREATION_STATE["result"] = result
                    if result.get("status") != "SUCCESS":
                        CREATION_STATE["error"] = result.get("error", "Generation failed")
            except Exception as e:
                with CREATION_LOCK:
                    CREATION_STATE["active"] = False
                    CREATION_STATE["status"] = "failed"
                    CREATION_STATE["error"] = str(e)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.send_json({"status": "STARTED", "topic": topic})

    def handle_maker_start(self, payload: dict):
        if shortsctl.daemon_running():
            pid = shortsctl.get_daemon_pid()
            return self.send_json({"status": "FAILED", "error": f"Already running (PID {pid})"})

        class Args:
            context = CONTEXT_FILE
            privacy = payload.get("privacy", "private")

        try:
            shortsctl.cmd_start(Args())
            time.sleep(0.5)
            running = shortsctl.daemon_running()
            pid = shortsctl.get_daemon_pid()
            self.send_json({"status": "SUCCESS", "running": running, "pid": pid})
        except Exception as e:
            self.send_json({"status": "FAILED", "error": str(e)}, 500)

    def handle_maker_stop(self):
        class Args:
            pass
        try:
            shortsctl.cmd_stop(Args())
            self.send_json({"status": "SUCCESS", "running": False})
        except Exception as e:
            self.send_json({"status": "FAILED", "error": str(e)}, 500)

    def serve_file(self, file_path: str, content_type: str, head_only: bool = False):
        if not os.path.exists(file_path):
            return self.send_error(404, "File not found")
        file_size = os.path.getsize(file_path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
            with open(file_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    self.wfile.write(chunk)

    def serve_media_with_range(self, file_path: str, head_only: bool = False):
        if not os.path.exists(file_path):
            return self.send_error(404, "Media not found")

        file_size = os.path.getsize(file_path)
        content_type, _ = mimetypes.guess_type(file_path)
        content_type = content_type or "video/mp4"

        range_header = self.headers.get("Range")
        if not range_header:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            if not head_only:
                with open(file_path, "rb") as f:
                    while chunk := f.read(64 * 1024):
                        self.wfile.write(chunk)
            return

        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not range_match:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        first_byte = int(range_match.group(1))
        last_byte = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        if first_byte >= file_size or last_byte >= file_size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        length = last_byte - first_byte + 1
        self.send_response(206)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {first_byte}-{last_byte}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        with open(file_path, "rb") as f:
            f.seek(first_byte)
            bytes_left = length
            while bytes_left > 0:
                chunk_size = min(bytes_left, 64 * 1024)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                self.wfile.write(chunk)
                bytes_left -= len(chunk)


def print_banner(host: str, port: int):
    lan_ip = get_local_ip()
    local_url = f"http://localhost:{port}"
    mobile_url = f"http://{lan_ip}:{port}"
    print("\n" + "=" * 60)
    print("   ⚡ AI SHORTS FACTORY - MOBILE CONTROL CENTER")
    print("=" * 60)
    print(f"  Laptop URL : {local_url}")
    print(f"  Mobile URL : {mobile_url}")
    print("-" * 60)
    print("  📱 To open on your iPhone or Android:")
    print(f"     1. Connect your phone to the same Wi-Fi")
    print(f"     2. Open Safari / Chrome and type: {mobile_url}")
    print("=" * 60 + "\n")


def run_server(port: int = 8088, host: str = "0.0.0.0"):
    os.makedirs(WEB_DIR, exist_ok=True)
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, DashboardHandler)
    print_banner(host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Shorts Factory Mobile Web Dashboard")
    parser.add_argument("--port", type=int, default=8088, help="Port to listen on (default: 8088)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host binding (default: 0.0.0.0)")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)
