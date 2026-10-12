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
import uuid
import argparse
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


def _login(cl, username: str, password: str) -> None:
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
        except (OSError, ValueError):
            pass
    cl.login(username, password)
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    cl.dump_settings(SESSION_FILE)


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
        _login(cl, username, password)
        username_ok = cl.username
        return {"status": "SUCCESS", "username": username_ok,
                "session": SESSION_FILE, "mode": "PRODUCTION"}
    except Exception as e:
        logger.error(f"Instagram connect failed: {e}")
        return {"status": "FAILED", "error": str(e)}


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

    try:
        cl = _new_client()
        _login(cl, username, password)
        media = cl.clip_upload(file_path, caption=caption, share_to_feed=share_to_feed)
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
        logger.error(f"Instagram upload failed: {e}")
        return {"status": "FAILED", "error": str(e)}


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
