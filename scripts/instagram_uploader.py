#!/usr/bin/env python3
"""
Instagram Uploader - AI Shorts Factory
Uploads the same edited Short to Instagram as a Reel, so one video lands on
both YouTube and Instagram. Uses the local file directly (no public URL needed),
which is why this works on a free setup with nothing hosted.

Credentials in .env: IG_USERNAME and IG_PASSWORD (the account you want to post to).
SHORTS_MOCK=1 gives a dry run with a fake link instead of posting.

A signed-in session is cached in logs/instagram_session.json after the first login,
so later posts usually skip the password step. Instagram does not offer "private
upload" through this route: a Reel is visible per your account's privacy, so on a
private account only your approved followers see it.

Note: instagrapi is an unofficial client. Keep your daily count modest
(set max_per_day in context.json) and warm gaps between posts.
"""

import os
import sys
import json
import time
import uuid
import argparse
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from scripts.log_sanitizer import redact as _redact
except ImportError:
    try:
        from log_sanitizer import redact as _redact
    except ImportError:
        def _redact(text: str) -> str:
            return text

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("instagram_uploader")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE = os.path.join(ROOT, os.getenv("LOG_PATH", "logs"), "instagram_session.json")


def mock_mode() -> bool:
    return os.getenv("SHORTS_MOCK", "").strip().lower() in ("1", "true", "yes")


def real_value(name: str):
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith(("your_", "mock_")):
        return None
    return value


def _new_client():
    from instagrapi import Client
    cl = Client()
    cl.delay_range = [2, 5]
    return cl


def _harden(path: str) -> None:
    """Session files hold login cookies: keep them readable by the owner only."""
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        logger.warning("Could not restrict permissions on %s: %s", path, _redact(str(exc)))


def _backup_session_file(reason: str) -> None:
    """Move a stale/unreadable cached session aside (never deleted) so a fresh login can be written."""
    if not os.path.exists(SESSION_FILE):
        return
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    backup = f"{SESSION_FILE}.bak-{reason}-{int(time.time())}"
    try:
        os.replace(SESSION_FILE, backup)
        _harden(backup)
        logger.warning("Cached Instagram session set aside as %s (%s)", backup, reason)
    except OSError as exc:
        logger.warning("Could not back up the cached Instagram session (%s)", _redact(str(exc)))


def _login_with_recovery(cl, username: str, password: str):
    """Sign in, reusing the cached session when possible.

    Instagram rejects long-lived cached sessions now and then (403/challenge/connection
    errors). When the cached session fails, it is backed up (not deleted) and one fresh
    login is attempted on a NEW client.

    Returns (active_client, mode) where mode is "cache" or "fresh". The returned client
    is the only one callers should use afterwards: a stale client is never reused, so
    cl.username / clip_upload always run on the session that actually logged in.
    """
    had_session = os.path.exists(SESSION_FILE)
    if had_session:
        try:
            cl.load_settings(SESSION_FILE)
        except Exception as exc:
            logger.warning("Cached Instagram session unreadable (%s); starting fresh", _redact(str(exc)))
            _backup_session_file("unreadable")
            had_session = False
    try:
        cl.login(username, password)
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        _harden(SESSION_FILE)
        return cl, ("cache" if had_session else "fresh")
    except Exception as exc:
        if not had_session:
            raise
        logger.warning("Login with the cached session failed (%s); retrying fresh", _redact(str(exc)))
        _backup_session_file("stale")
        cl = _new_client()
        cl.login(username, password)
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        _harden(SESSION_FILE)
        return cl, "fresh"


_CHALLENGE_HINTS = ("challenge", "checkpoint", "two_factor", "two-factor", "2fa", "verify")


def _error_kind(exc: Exception) -> str:
    """Classify an Instagram failure so the result can say what to do about it."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "twofactor" in name or "two_factor" in name or "two-factor" in text or "2fa" in text:
        return "two_factor"
    if "challenge" in name or any(h in text for h in _CHALLENGE_HINTS):
        return "challenge"
    if "rate" in name or "rate limit" in text or "429" in text or "too many" in text:
        return "rate_limited"
    if "login" in name or "logged_in" in name or "bad password" in text or "incorrect" in text:
        return "credentials"
    return "other"


_ADVICE = {
    "two_factor": ("Instagram asked for a two-factor code. Finish the login in the Instagram app "
                   "(or use the code from your authenticator/SMS), then run connect again."),
    "challenge": ("Instagram wants to verify this login. Open the Instagram app on the account's "
                  "phone, approve the login challenge, then run connect again."),
    "rate_limited": ("Instagram rate-limited this attempt. Wait a while before trying again and keep "
                     "the daily post count modest."),
    "credentials": ("Instagram rejected the login. Check IG_USERNAME and IG_PASSWORD in .env."),
}


def _friendly_error(exc: Exception) -> str:
    kind = _error_kind(exc)
    advice = _ADVICE.get(kind)
    # never echo raw credentials or session material, but keep the exception
    # class name so the failure stays diagnosable
    detail = _redact(f"{type(exc).__name__}: {exc}")
    if advice:
        return f"{advice} (Detail: {detail})"
    return detail


def connect_instagram() -> dict:
    """One-time check: sign in and cache the session so posting works unattended."""
    username, password = real_value("IG_USERNAME"), real_value("IG_PASSWORD")
    if not (username and password):
        return {
            "status": "FAILED",
            "error": ("Put IG_USERNAME and IG_PASSWORD in .env first "
                      "(the Instagram account you want to post Reels to)."),
        }
    if mock_mode():
        return {"status": "SUCCESS", "mode": "MOCK", "username": username}
    try:
        cl = _new_client()
        cl, reused = _login_with_recovery(cl, username, password)
        username_ok = cl.username
        return {"status": "SUCCESS", "username": username_ok, "login": reused,
                "session": SESSION_FILE, "mode": "PRODUCTION"}
    except Exception as e:
        logger.error("Instagram connect failed: %s", _redact(str(e)))
        return {"status": "FAILED", "error": _friendly_error(e), "error_kind": _error_kind(e)}


def upload_to_instagram(
    file_path: str,
    caption: str = "",
    share_to_feed: bool = True,
) -> dict:
    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Video file not found: {file_path}"}

    if mock_mode():
        logger.warning("SHORTS_MOCK is on: nothing is posted to Instagram.")
        mock_id = f"mock_{uuid.uuid4().hex[:10]}"
        return {
            "status": "SUCCESS",
            "media_id": mock_id,
            "instagram_url": f"https://instagram.com/reel/{mock_id}/",
            "caption": caption[:100],
            "upload_time_sec": 0,
            "mode": "MOCK",
        }

    username, password = real_value("IG_USERNAME"), real_value("IG_PASSWORD")
    if not (username and password):
        return {
            "status": "FAILED",
            "error": ("Instagram credentials are not set (IG_USERNAME, IG_PASSWORD). "
                      "Add them to .env and run `python scripts/shortsctl.py connect --platform instagram`. "
                      "Set SHORTS_MOCK=1 for a dry run."),
        }

    thumb_path = None
    created_thumb = False
    try:
        import subprocess
        candidate = f"{file_path}.ig_thumb.jpg"
        res = subprocess.run(
            ["ffmpeg", "-y", "-ss", "00:00:01", "-i", file_path, "-vframes", "1", "-q:v", "2", candidate],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res.returncode == 0 and os.path.exists(candidate):
            thumb_path = candidate
            created_thumb = True
    except Exception:
        pass

    try:
        cl = _new_client()
        cl, _login_mode = _login_with_recovery(cl, username, password)
        try:
            if thumb_path:
                media = cl.clip_upload(file_path, caption=caption, thumbnail=thumb_path, share_to_feed=share_to_feed)
            else:
                media = cl.clip_upload(file_path, caption=caption, share_to_feed=share_to_feed)
        except TypeError:
            if thumb_path:
                media = cl.clip_upload(file_path, caption=caption, thumbnail=thumb_path)
            else:
                media = cl.clip_upload(file_path, caption=caption)
        code = getattr(media, "code", "") or ""
        logger.info(f"Reel posted to Instagram. Code: {code}")
        return {
            "status": "SUCCESS",
            "media_id": str(getattr(media, "pk", "")),
            "instagram_url": f"https://www.instagram.com/reel/{code}/" if code else "",
            "caption": caption[:100],
            "mode": "PRODUCTION",
        }
    except Exception as e:
        logger.error("Instagram upload failed: %s", _redact(str(e)))
        return {"status": "FAILED", "error": _friendly_error(e), "error_kind": _error_kind(e)}
    finally:
        if created_thumb and thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="Upload video to Instagram as a Reel")
    parser.add_argument("--file", type=str, required=True, help="Path to video file to post")
    parser.add_argument("--caption", type=str, default="", help="Reel caption text")
    parser.add_argument("--metadata", type=str, default=None, help="JSON file from metadata_generator.py --output (title + description become the caption)")
    parser.add_argument("--no-feed", action="store_true", help="Reel only in the Reels tab, not on the profile grid")
    args = parser.parse_args()

    caption = args.caption
    if args.metadata:
        with open(args.metadata, encoding="utf-8") as f:
            meta = json.load(f)
        caption = f"{meta.get('title', '')}\n\n{meta.get('description', '')}".strip()
        tags = meta.get("tags") or []
        if tags:
            caption = f"{caption}\n\n" + " ".join(f"#{t.replace(' ', '')}" for t in tags[:10])

    result = upload_to_instagram(args.file, caption=caption, share_to_feed=not args.no_feed)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
