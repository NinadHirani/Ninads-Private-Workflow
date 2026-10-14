#!/usr/bin/env python3
"""
Content Finder Module - AI Shorts Factory
Searches Pexels (then Pixabay) for free, licensed portrait videos and picks the best candidate.
Both APIs are free; set PEXELS_API_KEY and/or PIXABAY_API_KEY. SHORTS_MOCK=1 uses a local sample instead.
"""

import os
import sys
import json
import argparse
import logging
import urllib.parse
import urllib.request
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text

logger = logging.getLogger("content_finder")

PEXELS_API_URL = "https://api.pexels.com/videos/search"
PIXABAY_API_URL = "https://pixabay.com/api/videos/"
MIN_DURATION = 5
MAX_DURATION = 60
MAX_HEIGHT = 1920  # no point downloading 4K for a 1080x1920 Short


def mock_mode() -> bool:
    return os.getenv("SHORTS_MOCK", "").strip().lower() in ("1", "true", "yes")


def real_key(name: str):
    """The env value, or None when it is missing or still a placeholder from .env.example."""
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith(("mock_", "your_")):
        return None
    return value


def _get_json(url: str, headers: dict = None, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-shorts-factory/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


try:
    from scripts.logger import get_used_asset_ids, is_asset_used
except ImportError:
    try:
        from logger import get_used_asset_ids, is_asset_used
    except ImportError:
        def get_used_asset_ids(): return set()
        def is_asset_used(asset_id): return False


def search_pexels(topic: str, per_page: int = 15, page: int = 1) -> list:
    api_key = real_key("PEXELS_API_KEY")
    if not api_key:
        return []
    query = urllib.parse.urlencode({"query": topic, "orientation": "portrait", "per_page": per_page, "page": page})
    try:
        data = _get_json(f"{PEXELS_API_URL}?{query}", {"Authorization": api_key})
    except Exception as e:
        logger.error("Pexels search failed: %s", redact(str(e)))
        return []
    return data.get("videos", [])


def search_pixabay(topic: str, per_page: int = 15, page: int = 1) -> list:
    """Pixabay results, reshaped to look like Pexels videos so one ranking function handles both."""
    api_key = real_key("PIXABAY_API_KEY")
    if not api_key:
        return []
    query = urllib.parse.urlencode({"key": api_key, "q": topic, "per_page": per_page, "page": page, "safesearch": "true"})
    try:
        data = _get_json(f"{PIXABAY_API_URL}?{query}")
    except Exception as e:
        logger.error("Pixabay search failed: %s", redact(str(e)))
        return []
    videos = []
    for hit in data.get("hits", []):
        files = [
            {"width": f.get("width"), "height": f.get("height"), "link": f.get("url")}
            for f in (hit.get("videos") or {}).values()
            if isinstance(f, dict) and f.get("url")
        ]
        videos.append({
            "id": f"pixabay_{hit.get('id')}",
            "duration": hit.get("duration", 0),
            "user": {"name": hit.get("user") or "Unknown Creator"},
            "video_files": files,
        })
    return videos


def find_videos(topic: str, page: int = 1) -> list:
    if mock_mode():
        logger.warning("SHORTS_MOCK is on: using the local sample video.")
        return get_mock_candidates(topic)
    videos = search_pexels(topic, page=page)
    if not videos:
        videos = search_pixabay(topic, page=page)
    return videos


def _dims(f: dict):
    return (f.get("width") or 0, f.get("height") or 0)


def _pick_file(video_files: list):
    """Best file for a vertical Short: portrait if any, the largest one up to 1920px tall."""
    usable = [f for f in video_files if f.get("link")]
    if not usable:
        return None, False
    portrait = [f for f in usable if _dims(f)[1] > _dims(f)[0]]
    pool = portrait or usable
    capped = [f for f in pool if _dims(f)[1] <= MAX_HEIGHT]
    if capped:
        best = max(capped, key=lambda f: _dims(f)[0] * _dims(f)[1])
    else:
        best = min(pool, key=lambda f: _dims(f)[0] * _dims(f)[1])
    return best, bool(portrait)


def rank_and_select_video(videos: list, exclude_used: bool = True):
    """The best candidate, skipping any previously used video assets to avoid repetition."""
    used_ids = get_used_asset_ids() if exclude_used else set()
    candidates = []
    for video in videos or []:
        vid_id = str(video.get("id"))
        if exclude_used and (vid_id in used_ids or f"pexels_{vid_id}" in used_ids or f"pixabay_{vid_id}" in used_ids):
            continue
        duration = video.get("duration", 0) or 0
        if duration < MIN_DURATION or duration > MAX_DURATION:
            continue
        best_file, is_portrait = _pick_file(video.get("video_files", []))
        if not best_file:
            continue
        if exclude_used and best_file.get("link") in used_ids:
            continue
        width, height = _dims(best_file)
        candidates.append(((is_portrait, width * height, -abs(30 - duration)), {
            "video_id": video.get("id"),
            "video_url": best_file.get("link"),
            "duration": duration,
            "width": width,
            "height": height,
            "user": (video.get("user") or {}).get("name", "Unknown Creator"),
        }))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def find_fresh_candidate(topic: str, max_pages: int = 5) -> dict:
    """Searches across pages to find a video candidate that has never been used."""
    if mock_mode():
        return rank_and_select_video(find_videos(topic), exclude_used=False)
    for p in range(1, max_pages + 1):
        videos = find_videos(topic, page=p)
        candidate = rank_and_select_video(videos, exclude_used=True)
        if candidate:
            return candidate
    logger.info("All candidates in first %d pages were previously used or unfit.", max_pages)
    return None


def get_mock_candidates(topic: str) -> list:
    """A local clip for offline runs and tests: SHORTS_SAMPLE_VIDEO if set, else tests/sample.mp4 (made by tests/conftest.py)."""
    sample_path = (os.getenv("SHORTS_SAMPLE_VIDEO") or "").strip() or os.path.join(os.path.dirname(__file__), "..", "tests", "sample.mp4")
    sample_path = os.path.abspath(sample_path)
    return [
        {
            "id": 855280,
            "duration": 22,
            "user": {"name": "Sample Clip"},
            "video_files": [
                {"id": 1, "quality": "hd", "width": 1080, "height": 1920, "link": f"file://{sample_path}"}
            ],
        }
    ]


def main():
    parser = argparse.ArgumentParser(description="Find portrait videos for YouTube Shorts")
    parser.add_argument("--topic", type=str, default="waterfall", help="Topic / keyword to search for")
    args = parser.parse_args()

    logger.info(f"Searching content for topic: '{args.topic}'")
    if not mock_mode() and not (real_key("PEXELS_API_KEY") or real_key("PIXABAY_API_KEY")):
        error = "No video API key set. Add a free PEXELS_API_KEY or PIXABAY_API_KEY to .env, or set SHORTS_MOCK=1 for an offline run."
        logger.error(error)
        print(json.dumps({"status": "FAILED", "error": error}))
        sys.exit(1)

    best_candidate = find_fresh_candidate(args.topic)
    if not best_candidate:
        logger.error("No valid video candidate found.")
        print(json.dumps({"status": "FAILED", "error": f"No usable {MIN_DURATION}-{MAX_DURATION}s video found for '{args.topic}'"}))
        sys.exit(1)

    logger.info(f"Selected candidate video ID {best_candidate['video_id']} ({best_candidate['width']}x{best_candidate['height']}, {best_candidate['duration']}s)")
    print(json.dumps({"status": "SUCCESS", "topic": args.topic, "candidate": best_candidate}, indent=2))


if __name__ == "__main__":
    main()
