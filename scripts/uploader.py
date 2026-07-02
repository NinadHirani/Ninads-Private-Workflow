#!/usr/bin/env python3
"""
Uploader Module - AI Shorts Factory
Uploads edited video files to YouTube Shorts via YouTube Data API v3.
Implements retry logic and mock upload mode when credentials are not configured.
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

def upload_to_youtube(
    file_path: str,
    title: str = "AI Shorts Factory Video #Shorts",
    description: str = "Automated YouTube Short",
    privacy_status: str = "unlisted",
    retries: int = 3
) -> dict:
    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Video file not found: {file_path}"}
        
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
    
    is_mock = (
        not client_id or client_id.startswith("mock_") or
        not client_secret or client_secret.startswith("mock_") or
        not refresh_token or refresh_token.startswith("mock_")
    )
    
    if is_mock:
        logger.warning("YouTube API credentials missing or mock. Running in Mock Upload mode.")
        mock_id = f"mock_{uuid.uuid4().hex[:10]}"
        return {
            "status": "SUCCESS",
            "video_id": mock_id,
            "youtube_url": f"https://youtube.com/shorts/{mock_id}",
            "title": title,
            "privacy_status": privacy_status,
            "upload_time_sec": 1.25,
            "mode": "MOCK"
        }
        
    # Real YouTube API upload implementation using Google OAuth2
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        
        youtube = build("youtube", "v3", credentials=credentials)
        
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": ["shorts", "Shorts", "automation"],
                "categoryId": "22" # People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        
        start_time = time.time()
        response = None
        
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Uploading video to YouTube (Attempt {attempt}/{retries})...")
                status, response = request.next_chunk()
                if response is not None and "id" in response:
                    video_id = response["id"]
                    upload_duration = time.time() - start_time
                    logger.info(f"Video uploaded successfully! Video ID: {video_id}")
                    return {
                        "status": "SUCCESS",
                        "video_id": video_id,
                        "youtube_url": f"https://youtube.com/shorts/{video_id}",
                        "title": title,
                        "privacy_status": privacy_status,
                        "upload_time_sec": round(upload_duration, 2),
                        "mode": "PRODUCTION"
                    }
            except Exception as upload_err:
                logger.warning(f"Upload attempt {attempt} error: {upload_err}")
                if attempt < retries:
                    time.sleep(attempt * 4)
                    
        return {"status": "FAILED", "error": "YouTube upload failed after all retries"}
        
    except Exception as e:
        logger.error(f"YouTube API setup error: {e}")
        return {"status": "FAILED", "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube Shorts")
    parser.add_argument("--file", type=str, required=True, help="Path to video file to upload")
    parser.add_argument("--title", type=str, default="Nature Views #Shorts", help="Video Title")
    parser.add_argument("--description", type=str, default="Relaxing views #shorts", help="Video Description")
    parser.add_argument("--privacy", type=str, default="unlisted", help="Privacy status (unlisted/public/private)")
    args = parser.parse_args()
    
    result = upload_to_youtube(args.file, args.title, args.description, args.privacy)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)

if __name__ == "__main__":
    main()
