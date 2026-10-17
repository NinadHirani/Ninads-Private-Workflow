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
import hmac
import secrets
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

import scripts.shortsctl as shortsctl
from scripts.story_pipeline import run_story
from scripts.scene_generator import classify_topic

WEB_DIR = os.path.join(ROOT, "web")
LOG_DIR = os.path.join(ROOT, os.getenv("LOG_PATH", "logs"))
DAEMON_LOG = os.path.join(LOG_DIR, "auto.log")
STATE_FILE = os.path.join(LOG_DIR, "auto_state.json")
CONTEXT_FILE = os.path.join(ROOT, "context.json")
DELIVERABLES_DIR = os.path.join(ROOT, "deliverables")

# Web UI access control. Every API endpoint and media file requires one of:
# a SHORTS_UI_TOKEN header (X-Shorts-Token or 'Authorization: Bearer'), an
# HttpOnly session cookie minted by POST /api/session in exchange for that
# token (the dashboard's one-time login), or the request coming from the
# machine itself (loopback source address AND a loopback Host). Browser
# fetch metadata (Origin, Sec-Fetch-Site) is NOT accepted as proof of
# anything: raw HTTP clients can forge both, so they never authorize.
UI_TOKEN_ENV = "SHORTS_UI_TOKEN"
SESSION_COOKIE = "shorts_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600


def ui_token():
    value = (os.getenv(UI_TOKEN_ENV) or "").strip()
    if not value or value.startswith(("your_", "mock_")):
        return None
    return value


# In-memory dashboard sessions. POST /api/session trades SHORTS_UI_TOKEN for a
# random HttpOnly cookie so the browser never holds the token in JS or storage.
# Sessions live in this process only: restarting the web UI logs devices out.
_SESSIONS = {}  # cookie value -> expiry epoch seconds
_SESSIONS_LOCK = threading.Lock()
_MAX_SESSIONS = 50


def _issue_session() -> str:
    value = secrets.token_urlsafe(32)
    now = time.time()
    with _SESSIONS_LOCK:
        for key in [k for k, exp in _SESSIONS.items() if exp <= now]:
            _SESSIONS.pop(key, None)
        if len(_SESSIONS) >= _MAX_SESSIONS:
            _SESSIONS.pop(min(_SESSIONS, key=_SESSIONS.get), None)
        _SESSIONS[value] = now + SESSION_TTL_SECONDS
    return value


def _revoke_session(value: str) -> None:
    if not value:
        return
    with _SESSIONS_LOCK:
        for key in list(_SESSIONS):
            if hmac.compare_digest(key, value):
                _SESSIONS.pop(key, None)


def _session_valid(value: str) -> bool:
    if not value:
        return False
    now = time.time()
    with _SESSIONS_LOCK:
        for key, expiry in _SESSIONS.items():
            if hmac.compare_digest(key, value):
                if expiry > now:
                    _SESSIONS[key] = now + SESSION_TTL_SECONDS  # sliding renewal
                    return True
                _SESSIONS.pop(key, None)
                return False
    return False

# Failed-login rate limit for POST /api/session. Every remote caller arrives
# through one local tunnel process, so a per-IP limit would be meaningless;
# the limit is global and rolling. A correct token is never held back, so the
# owner can always log in; only wrong tokens consume and trip the limit.
SESSION_FAIL_WINDOW_SECONDS = 15 * 60
SESSION_FAIL_LIMIT = 10
_FAILED_LOGINS = []  # epoch seconds of recent wrong-token attempts
_FAILED_LOGINS_LOCK = threading.Lock()


def _prune_failed_logins(now: float) -> None:
    while _FAILED_LOGINS and _FAILED_LOGINS[0] <= now - SESSION_FAIL_WINDOW_SECONDS:
        _FAILED_LOGINS.pop(0)


def _record_failed_login() -> float:
    """Record a wrong-token login attempt; returns the seconds until wrong
    attempts are accepted again (0 while still under the limit)."""
    now = time.time()
    with _FAILED_LOGINS_LOCK:
        _prune_failed_logins(now)
        _FAILED_LOGINS.append(now)
        if len(_FAILED_LOGINS) > SESSION_FAIL_LIMIT:
            return max(1.0, SESSION_FAIL_WINDOW_SECONDS - (now - _FAILED_LOGINS[0]))
        return 0.0


def _clear_failed_logins() -> None:
    with _FAILED_LOGINS_LOCK:
        _FAILED_LOGINS.clear()


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
    "continuous": False,
    "count": 0,
    "stop_requested": False,
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

    def send_json(self, data: dict, status: int = 200, head_only: bool = False,
                  extra_headers: dict = None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self._apply_cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight is answered openly: it grants nothing by itself and
        # carries no data, and the actual GET/POST that follows is still
        # authenticated. Without this, a browser preflight for the
        # X-Shorts-Token header from another origin (the Vercel app) would be
        # refused and the authorized call could never be made.
        self.send_response(200)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        requested = (self.headers.get("Access-Control-Request-Headers") or "").strip()
        self.send_header("Access-Control-Allow-Headers",
                         requested or "Content-Type, X-Shorts-Token, Authorization, Bypass-Tunnel-Reminder")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head_only=True)

    # --- access control -----------------------------------------------------
    CONTROL_PATHS = ("/api/maker/start", "/api/maker/stop", "/api/config", "/api/create", "/api/create/stop", "/api/series/next")
    LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")

    def _host_bare(self) -> str:
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return ""
        if host.startswith("["):
            end = host.find("]")
            return host[1:end] if end != -1 else host
        return host.rsplit(":", 1)[0]

    def _loopback_client(self) -> bool:
        try:
            ip = (self.client_address[0] or "").strip()
        except Exception:
            return False
        return ip == "::1" or ip.startswith("127.") or ip.startswith("::ffff:127.")

    def _local_host(self) -> bool:
        # The Host header alone is client-controlled: a LAN attacker can send
        # "Host: localhost" verbatim. Loopback is required on the connection
        # itself. The public tunnel also connects from 127.0.0.1 but carries
        # the public Host name, so it stays "outside" and must authenticate.
        return self._host_bare() in self.LOOPBACK_HOSTS and self._loopback_client()

    def _same_origin(self):
        """True/False when an Origin header is present; None when it is absent."""
        origin = self.headers.get("Origin")
        if not origin:
            return None
        try:
            return urlparse(origin).netloc.lower() == (self.headers.get("Host") or "").strip().lower()
        except ValueError:
            return False

    def _session_cookie_value(self) -> str:
        raw = self.headers.get("Cookie") or ""
        try:
            jar = SimpleCookie()
            jar.load(raw)
        except Exception:
            return ""
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _origin_host_mismatch(self) -> bool:
        """True when the request carries an Origin that does not match the
        Host it was sent to. Origin is never accepted AS authorization (raw
        clients forge it), but a visible mismatch is evidence of a browser
        drive-by (cross-site fetch/form from another website), so an
        uncredentialed mismatched request is rejected outright. A matching
        or absent Origin proves nothing and grants nothing."""
        origin = self.headers.get("Origin")
        if not origin:
            return False
        try:
            return urlparse(origin).netloc.lower() != (self.headers.get("Host") or "").strip().lower()
        except ValueError:
            return True

    def _authorized(self) -> bool:
        """One of three proofs: the machine itself (loopback client AND
        loopback Host, and no cross-site Origin), the SHORTS_UI_TOKEN header
        (X-Shorts-Token or Bearer), or a valid dashboard session cookie.
        Origin and Sec-Fetch-Site never grant access on their own; a
        mismatched Origin only adds a rejection for uncredentialed callers.
        No token configured and no session means fail closed."""
        supplied = (self.headers.get("X-Shorts-Token") or "").strip()
        auth = (self.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer ") and not supplied:
            supplied = auth[7:].strip()
        token = ui_token()
        if token and supplied and hmac.compare_digest(supplied, token):
            return True
        if _session_valid(self._session_cookie_value()):
            return True
        if self._origin_host_mismatch():
            return False
        return self._local_host()

    def _control_allowed(self) -> bool:
        """State-changing endpoints use the same proof as reads: token header,
        dashboard session, or the machine itself. No same-origin or
        Sec-Fetch shortcut: those headers are forgeable by raw clients."""
        return self._authorized()

    def _cors_origin(self) -> str | None:
        """Echo the request Origin for same-origin, authorized callers, or known dashboard origins;
        unauthorized cross-origin pages (like evil.example) get no ACAO header."""
        origin = self.headers.get("Origin")
        if not origin:
            return None
        if self._same_origin() or self._authorized() or self.path == "/api/session":
            return origin
        try:
            parsed_origin = urlparse(origin)
            netloc = parsed_origin.netloc.lower().split(":", 1)[0]
            if netloc.endswith(".vercel.app") or netloc == "vercel.app" or netloc in self.LOOPBACK_HOSTS:
                return origin
        except ValueError:
            pass
        return None

    def _apply_cors(self):
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    # Read endpoints that expose private state (config, logs, the deliverable
    # list and the media files themselves) use the same proof as the
    # state-changing ones: SHORTS_UI_TOKEN header, dashboard session cookie,
    # or the machine itself. Origin and Sec-Fetch-Site are deliberately NOT
    # trusted: any raw HTTP client can forge both, and a forged pair once
    # granted full read access through the public tunnel. The dashboard logs
    # in once (POST /api/session with the token) and receives an HttpOnly
    # cookie, so fetch() and <video> keep working without JS holding the
    # token. Static assets stay public so the page itself always loads; the
    # token never appears in responses, links, or the served page.
    def _read_allowed(self) -> bool:
        return self._authorized()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/session":
            self.send_error(404, "Not Found")
            return
        if not self._authorized():
            self.send_json({"status": "FAILED", "error": "Unauthorized."}, 401)
            return
        _revoke_session(self._session_cookie_value())
        self.send_json({"status": "ok", "detail": "session closed"}, 200)

    def do_GET(self, head_only: bool = False):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.serve_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8", head_only=head_only)
        elif path in ("/manifest.json", "/sw.js", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"):
            rel_path = path.lstrip("/")
            mime = "application/manifest+json" if path.endswith(".json") else (
                "application/javascript" if path.endswith(".js") else "image/png"
            )
            self.serve_file(os.path.join(WEB_DIR, rel_path), mime, head_only=head_only)
        elif path.startswith("/api/") or path.startswith("/deliverables/"):
            if not self._read_allowed():
                self.send_json({
                    "status": "FAILED",
                    "error": ("Unauthorized. Sign in once on the dashboard with the SHORTS_UI_TOKEN "
                              "(it sets a session cookie), or send that token from .env as the "
                              "X-Shorts-Token header or 'Authorization: Bearer <token>'."),
                }, 401, head_only=head_only)
                return
            if path.startswith("/deliverables/"):
                filename = os.path.basename(path)
                file_path = os.path.join(DELIVERABLES_DIR, filename)
                if not os.path.isfile(file_path):
                    # basename already blocks directory traversal; this turns
                    # paths like /deliverables/.. into a clean 404 instead of
                    # a server error on a directory read.
                    self.send_error(404, "Media not found")
                    return
                self.serve_media_with_range(file_path, head_only=head_only)
            elif path == "/api/status":
                self.handle_api_status()
            elif path == "/api/logs":
                self.handle_api_logs(parsed)
            elif path == "/api/deliverables":
                self.handle_api_deliverables()
            elif path == "/api/config":
                self.handle_api_get_config()
            elif path == "/api/queue":
                self.handle_api_queue()
            elif path == "/api/classify":
                self.handle_api_classify(parsed)
            elif path == "/api/create/status":
                self.handle_api_create_status()
            elif path == "/api/series/status":
                self.handle_api_series_status(parsed)
            elif path == "/api/series/list":
                self.handle_api_series_list()
            else:
                self.send_error(404, "Not Found")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        # Gate after the body is drained: rejecting earlier would close the
        # socket with unread request data, which sends a TCP reset that can
        # clobber the 401 response on the wire.
        if path == "/api/session":
            # The one-time login: it authenticates with the token itself, so
            # it must be reachable before any session exists. CSRF-safe: a
            # forged request without the real token is rejected inside.
            try:
                payload_session = json.loads(body) if body else {}
            except Exception:
                payload_session = {}
            self.handle_api_session(payload_session)
            return
        if path in DashboardHandler.CONTROL_PATHS and not self._control_allowed():
            self.send_json({
                "status": "FAILED",
                "error": ("Unauthorized. Sign in once on the dashboard with the SHORTS_UI_TOKEN "
                          "(it sets a session cookie), or send that token from .env as the "
                          "X-Shorts-Token header or 'Authorization: Bearer <token>'."),
            }, 401)
            return
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
        elif path == "/api/create/stop":
            self.handle_api_create_stop()
        elif path == "/api/series/next":
            self.handle_api_series_next(payload)
        else:
            self.send_error(404, "Not Found")

    def handle_api_session(self, payload: dict):
        """One-time dashboard login: trade SHORTS_UI_TOKEN for an HttpOnly
        session cookie. The token is verified with a constant-time compare,
        never echoed back, never logged, and never stored in JS or the page."""
        supplied = str(payload.get("token") or "").strip()
        token = ui_token()
        if not token or not supplied or not hmac.compare_digest(supplied, token):
            limited = _record_failed_login()
            if limited > 0:
                retry_after = int(limited + 1)
                self.send_json(
                    {"status": "FAILED",
                     "error": "Too many failed logins. Try again in %d seconds." % retry_after},
                    429, extra_headers={"Retry-After": str(retry_after)})
                return
            self.send_json({"status": "FAILED", "error": "Invalid access token."}, 401)
            return
        _clear_failed_logins()
        value = _issue_session()
        cookie = (f"{SESSION_COOKIE}={value}; Path=/; Max-Age={SESSION_TTL_SECONDS}; "
                  "HttpOnly; SameSite=Strict")
        https = (self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https"
        if https or not self._is_private_host():
            cookie += "; Secure"
        self.send_json({"status": "ok", "detail": "session established"}, 200,
                       extra_headers={"Set-Cookie": cookie})

    def _is_private_host(self) -> bool:
        """True when the Host names the machine or the LAN, where plain-HTTP
        dashboard use is normal. Any other Host (the public tunnel, a public
        domain) gets a Secure session cookie, so the browser never sends the
        cookie over an accidental plain-HTTP downgrade of that address."""
        host = self._host_bare()
        if not host:
            return True
        if host in self.LOOPBACK_HOSTS or host.endswith(".local"):
            return True
        labels = host.split(".")
        if len(labels) == 4 and all(part.isdigit() for part in labels):
            first, second = int(labels[0]), int(labels[1])
            if (first == 10 or (first == 192 and second == 168)
                    or (first == 172 and 16 <= second <= 31)
                    or (first == 169 and second == 254)):
                return True
        return False

    def handle_api_queue(self):
        """Read-only view of the dual-upload queue (diagnostics only; there is
        no automatic drain, see README)."""
        try:
            from scripts.uploader import get_dual_queue
            entries = get_dual_queue()
        except Exception as exc:
            entries = {"error": f"{type(exc).__name__}: queue unavailable"}
        self.send_json({"status": "ok", "queue": entries}, 200)

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
        try:
            num_lines = int(qs.get("lines", ["60"])[0])
        except (TypeError, ValueError):
            num_lines = 60
        num_lines = max(1, min(num_lines, 500))
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
                    topic_title = meta.get("title") or meta.get("topic")
                    if not topic_title:
                        if fname.startswith("series_"):
                            parts = fname.split("_")
                            topic_title = f"{parts[1].title()} - Episode {parts[2].upper()}" if len(parts) >= 3 else fname
                        else:
                            topic_title = fname.replace("short_", "").rsplit("_", 1)[0].replace("_", " ")

                    items.append({
                        "filename": fname,
                        "url": f"/deliverables/{fname}",
                        "size_bytes": stat.st_size,
                        "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "topic": topic_title,
                        "metadata": meta.get("metadata", {}),
                        "duration": meta.get("duration") or meta.get("duration_sec", 30),
                        "category": meta.get("era") or meta.get("category", "general"),
                        "style": meta.get("style", "cinematic"),
                        "privacy": meta.get("privacy", "private"),
                        "series_id": meta.get("series_id"),
                        "episode": meta.get("episode"),
                        "era": meta.get("era"),
                        "cliffhanger": meta.get("cliffhanger"),
                    })
        items.sort(key=lambda x: x["created_at"], reverse=True)
        self.send_json({"items": items})

    def handle_api_series_status(self, parsed):
        qs = parse_qs(parsed.query)
        series_id = qs.get("series", ["kane"])[0]
        from scripts.series_manager import load_series, get_current_era, init_series
        st = load_series(series_id) or init_series(series_id)
        era = get_current_era(st)
        self.send_json({
            "series_id": st.get("series_id"),
            "title": st.get("title"),
            "current_episode": st.get("current_episode", 1),
            "timeline_day": st.get("timeline_day", 1),
            "era": era.get("name"),
            "era_subtitle": era.get("subtitle"),
            "character": st.get("character"),
            "last_cliffhanger": st.get("last_cliffhanger"),
            "total_episodes": len(st.get("episode_history", [])),
            "history": st.get("episode_history", [])[-10:],
        })

    def handle_api_series_list(self):
        from scripts.series_manager import list_all_series
        self.send_json({"series": list_all_series()})

    def handle_api_series_next(self, payload: dict):
        global CREATION_STATE
        series_id = (payload.get("series_id") or "kane").strip()
        duration = int(payload.get("duration", 40))

        with CREATION_LOCK:
            if CREATION_STATE["active"]:
                return self.send_json({"status": "FAILED", "error": f"Another creation is already running: '{CREATION_STATE['topic']}'"}, 409)
            CREATION_STATE["active"] = True
            CREATION_STATE["topic"] = f"Series: {series_id.title()}"
            CREATION_STATE["step"] = "init"
            CREATION_STATE["status"] = "running"
            CREATION_STATE["detail"] = f"Generating next continuous episode for {series_id.title()}..."
            CREATION_STATE["error"] = None
            CREATION_STATE["result"] = None
            CREATION_STATE["stop_requested"] = False
            CREATION_STATE["deliverable_filename"] = None

        def worker():
            from scripts.series_pipeline import produce_episode
            def on_progress(step, status, detail=None):
                with CREATION_LOCK:
                    CREATION_STATE["step"] = step
                    CREATION_STATE["status"] = status
                    if detail:
                        CREATION_STATE["detail"] = str(detail)

            try:
                res = produce_episode(series_id=series_id, target_duration=duration, on_progress=on_progress)
                with CREATION_LOCK:
                    CREATION_STATE["result"] = res
                    CREATION_STATE["active"] = False
                    if res.get("status") == "SUCCESS":
                        CREATION_STATE["status"] = "done"
                        CREATION_STATE["count"] = CREATION_STATE.get("count", 0) + 1
                        if res.get("video_file"):
                            CREATION_STATE["deliverable_filename"] = os.path.basename(res["video_file"])
                        CREATION_STATE["detail"] = f"Episode #{res.get('episode')} produced successfully: '{res.get('title')}'!"
                    else:
                        CREATION_STATE["status"] = "failed"
                        CREATION_STATE["error"] = res.get("error", "Failed to produce episode")
            except Exception as e:
                with CREATION_LOCK:
                    CREATION_STATE["active"] = False
                    CREATION_STATE["status"] = "failed"
                    CREATION_STATE["error"] = str(e)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.send_json({"status": "STARTED", "series_id": series_id})

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

    def handle_api_create_stop(self):
        global CREATION_STATE
        with CREATION_LOCK:
            CREATION_STATE["stop_requested"] = True
            CREATION_STATE["detail"] = "Stopping creation after current video completes..."
        self.send_json({"status": "STOPPING", "count": CREATION_STATE.get("count", 0)})

    def handle_api_create(self, payload: dict):
        global CREATION_STATE
        raw_topic = (payload.get("topic") or "").strip()
        if not raw_topic:
            return self.send_json({"status": "FAILED", "error": "Topic cannot be empty"}, 400)

        topic_lines = [line.strip() for line in raw_topic.splitlines() if line.strip()]
        topic = topic_lines[0] if topic_lines else raw_topic
        continuous = bool(payload.get("continuous", len(topic_lines) > 1))

        with CREATION_LOCK:
            if CREATION_STATE["active"]:
                return self.send_json({"status": "FAILED", "error": f"Another creation is already running: '{CREATION_STATE['topic']}'"}, 409)

            duration = int(payload.get("duration") or 45)
            privacy = payload.get("privacy") or "public"
            upload = bool(payload.get("upload", True))
            audio_mode = payload.get("audio_mode")

            CREATION_STATE["active"] = True
            CREATION_STATE["topic"] = topic
            CREATION_STATE["step"] = "init"
            CREATION_STATE["status"] = "running"
            CREATION_STATE["detail"] = f"Initializing pipeline for '{topic}'"
            CREATION_STATE["started_at"] = time.time()
            CREATION_STATE["result"] = None
            CREATION_STATE["error"] = None
            CREATION_STATE["continuous"] = continuous
            CREATION_STATE["count"] = 0
            CREATION_STATE["stop_requested"] = False
            CREATION_STATE["deliverable_filename"] = None

        def worker():
            global CREATION_STATE
            if audio_mode and audio_mode != "auto":
                os.environ["AUDIO_MODE"] = audio_mode
            elif "AUDIO_MODE" in os.environ:
                del os.environ["AUDIO_MODE"]

            context_topics = []
            niche_context = ""
            if os.path.exists(CONTEXT_FILE):
                try:
                    with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        context_topics = cfg.get("topics", [])
                        niche_context = cfg.get("context", "")
                except Exception:
                    pass

            from scripts.auto_run import topic_iterator
            if len(topic_lines) > 1:
                seed_pool = topic_lines
            else:
                seed_pool = [topic] + [t for t in context_topics if t != topic]
            topic_gen = topic_iterator(seed_pool, niche_context=niche_context)
            current_topic = topic

            while True:
                with CREATION_LOCK:
                    if CREATION_STATE["stop_requested"]:
                        CREATION_STATE["active"] = False
                        CREATION_STATE["status"] = "stopped"
                        CREATION_STATE["detail"] = f"Creation stopped. Total made: {CREATION_STATE['count']}."
                        break
                    CREATION_STATE["topic"] = current_topic
                    CREATION_STATE["step"] = "init"
                    CREATION_STATE["status"] = "running"
                    CREATION_STATE["detail"] = f"Generating video #{CREATION_STATE['count'] + 1}: '{current_topic}'"

                def on_progress(step, status, detail=None):
                    with CREATION_LOCK:
                        CREATION_STATE["step"] = step
                        CREATION_STATE["status"] = status
                        if detail:
                            CREATION_STATE["detail"] = str(detail)

                try:
                    result = run_story(
                        topic=current_topic,
                        duration=duration,
                        privacy=privacy,
                        upload=upload,
                        on_progress=on_progress,
                    )
                    with CREATION_LOCK:
                        if result.get("status") == "SUCCESS":
                            CREATION_STATE["count"] += 1
                            if result.get("deliverable_file"):
                                CREATION_STATE["deliverable_filename"] = os.path.basename(result["deliverable_file"])
                        CREATION_STATE["result"] = result
                        if result.get("status") != "SUCCESS":
                            CREATION_STATE["error"] = result.get("error", "Generation failed")
                except Exception as e:
                    with CREATION_LOCK:
                        CREATION_STATE["error"] = str(e)

                with CREATION_LOCK:
                    if not continuous or CREATION_STATE["stop_requested"]:
                        CREATION_STATE["active"] = False
                        CREATION_STATE["status"] = "done" if not CREATION_STATE.get("error") else "failed"
                        break
                    if len(topic_lines) > 1 and CREATION_STATE["count"] >= len(topic_lines) and payload.get("continuous") is None:
                        CREATION_STATE["active"] = False
                        CREATION_STATE["status"] = "done"
                        break
                    CREATION_STATE["step"] = "next_queued"
                    CREATION_STATE["detail"] = f"Video #{CREATION_STATE['count']} completed! Preparing next video..."

                time.sleep(3)
                try:
                    current_topic = next(topic_gen)
                except Exception:
                    current_topic = f"{topic} (Edition {CREATION_STATE['count'] + 1})"

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.send_json({"status": "STARTED", "topic": topic, "continuous": continuous})

    def handle_maker_start(self, payload: dict):
        if shortsctl.daemon_running():
            pid = shortsctl.get_daemon_pid()
            return self.send_json({"status": "FAILED", "error": f"Already running (PID {pid})"})

        class Args:
            context = CONTEXT_FILE
            privacy = payload.get("privacy", "public")

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
        self._apply_cors()
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
            try:
                with open(file_path, "rb") as f:
                    while chunk := f.read(64 * 1024):
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

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
            self._apply_cors()
            self.end_headers()
            if not head_only:
                try:
                    with open(file_path, "rb") as f:
                        while chunk := f.read(64 * 1024):
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return

        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not range_match:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self._apply_cors()
            self.end_headers()
            return

        first_byte = int(range_match.group(1))
        last_byte = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        if first_byte >= file_size or last_byte >= file_size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self._apply_cors()
            self.end_headers()
            return

        length = last_byte - first_byte + 1
        self.send_response(206)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {first_byte}-{last_byte}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self._apply_cors()
        self.end_headers()

        try:
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
        except (BrokenPipeError, ConnectionResetError):
            pass


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
