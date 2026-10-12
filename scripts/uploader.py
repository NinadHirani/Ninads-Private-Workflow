#!/usr/bin/env python3
"""
Uploader Module - AI Shorts Factory
Uploads an edited Short through the YouTube Data API v3 (resumable upload with retries).
Missing credentials are an error; SHORTS_MOCK=1 gives a dry run with a fake video ID instead.
"""

import os
import sys
import time
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
logger = logging.getLogger("uploader")

PRIVACY_OPTIONS = ("public", "unlisted", "private")
RETRIABLE_STATUS = (500, 502, 503, 504)


def mock_mode() -> bool:
    return os.getenv("SHORTS_MOCK", "").strip().lower() in ("1", "true", "yes")


def real_value(name: str):
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith(("mock_", "your_")):
        return None
    return value


def load_metadata(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: data[k] for k in ("title", "description", "tags") if k in data}


def upload_to_youtube(
    file_path: str,
    title: str = "AI Shorts Factory Video #Shorts",
    description: str = "Automated YouTube Short",
    privacy_status: str = "unlisted",
    tags: list = None,
    retries: int = 3,
    publish_at: str = None,
) -> dict:
    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Video file not found: {file_path}"}
    if privacy_status not in PRIVACY_OPTIONS:
        return {"status": "FAILED", "error": f"Privacy must be one of {', '.join(PRIVACY_OPTIONS)}"}
    tags = tags or ["shorts"]

    if mock_mode():
        logger.warning("SHORTS_MOCK is on: nothing is uploaded.")
        mock_id = f"mock_{uuid.uuid4().hex[:10]}"
        return {
            "status": "SUCCESS",
            "video_id": mock_id,
            "youtube_url": f"https://youtube.com/shorts/{mock_id}",
            "title": title,
            "privacy_status": "private" if publish_at else privacy_status,
            "publish_at": publish_at,
            "upload_time_sec": 0,
            "mode": "MOCK",
        }

    client_id = real_value("YOUTUBE_CLIENT_ID")
    client_secret = real_value("YOUTUBE_CLIENT_SECRET")
    refresh_token = real_value("YOUTUBE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        return {
            "status": "FAILED",
            "error": "YouTube credentials are not set (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN). Set SHORTS_MOCK=1 for a dry run.",
        }

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        return {"status": "FAILED", "error": "google-api-python-client is not installed (pip install -r docker/python/requirements.txt)"}

    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
        youtube = build("youtube", "v3", credentials=credentials)
        status_body = {
            "privacyStatus": "private" if publish_at else privacy_status,
            "selfDeclaredMadeForKids": False,
        }
        if publish_at:
            status_body["publishAt"] = publish_at

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": os.getenv("YOUTUBE_CATEGORY_ID", "22"),  # 22 = People & Blogs
            },
            "status": status_body,
        }
        media = MediaFileUpload(file_path, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        start_time = time.time()
        response = None
        failures = 0
        import socket
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(120)
        try:
            while response is None:
                try:
                    _, response = request.next_chunk()
                except HttpError as e:
                    # If YouTube rejects publishAt (e.g. unverified for scheduled publishing), fallback to private
                    if publish_at and ("publishAt" in str(e) or "scheduled" in str(e).lower()):
                        logger.warning("YouTube rejected scheduled publishAt (%s). Retrying as private without schedule.", e)
                        return upload_to_youtube(file_path, title, description, privacy_status="private",
                                                 tags=tags, retries=retries, publish_at=None)
                    err_content = str(e).lower()
                    if (e.resp.status in (400, 403)) and any(k in err_content for k in ("quotaexceeded", "uploadlimitexceeded", "daily limit", "exceeded the number of videos")):
                        logger.warning("YouTube daily upload quota or upload limit reached: %s", e)
                        return {
                            "status": "QUOTA_EXCEEDED",
                            "error": "YouTube daily upload limit exceeded (channel limit or quota reached).",
                            "quota_exceeded": True,
                        }
                    if e.resp.status not in RETRIABLE_STATUS or failures >= retries:
                        raise
                    failures += 1
                    logger.warning(f"YouTube returned {e.resp.status}, retrying ({failures}/{retries})")
                    time.sleep(2 ** failures)
                except (OSError, TimeoutError, socket.timeout) as e:
                    if failures >= retries:
                        raise
                    failures += 1
                    logger.warning(f"Network error during upload ({e}), retrying ({failures}/{retries})")
                    time.sleep(2 ** failures)
        finally:
            socket.setdefaulttimeout(old_timeout)

        if "id" not in response:
            return {"status": "FAILED", "error": f"Unexpected YouTube response: {response}"}
        video_id = response["id"]
        logger.info(f"Video uploaded successfully! Video ID: {video_id} (privacy: {status_body['privacyStatus']}, publish_at: {publish_at})")
        return {
            "status": "SUCCESS",
            "video_id": video_id,
            "youtube_url": f"https://youtube.com/shorts/{video_id}",
            "title": title,
            "privacy_status": status_body["privacyStatus"],
            "publish_at": publish_at,
            "upload_time_sec": round(time.time() - start_time, 2),
            "mode": "PRODUCTION",
        }
    except Exception as e:
        logger.error(f"YouTube upload failed: {e}")
        return {"status": "FAILED", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube Shorts")
    parser.add_argument("--file", type=str, required=True, help="Path to video file to upload")
    parser.add_argument("--metadata", type=str, default=None, help="JSON file from metadata_generator.py --output (title, description, tags)")
    parser.add_argument("--title", type=str, default="Nature Views #Shorts", help="Video title (ignored when --metadata is given)")
    parser.add_argument("--description", type=str, default="Relaxing views #shorts", help="Video description (ignored when --metadata is given)")
    parser.add_argument("--tags", type=str, default="shorts", help="Comma-separated tags (ignored when --metadata is given)")
    parser.add_argument("--privacy", type=str, default="unlisted", choices=PRIVACY_OPTIONS, help="Privacy status")
    args = parser.parse_args()

    title, description = args.title, args.description
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if args.metadata:
        meta = load_metadata(args.metadata)
        title = meta.get("title", title)
        description = meta.get("description", description)
        tags = meta.get("tags", tags)

    result = upload_to_youtube(args.file, title, description, args.privacy, tags)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
