#!/usr/bin/env python3
"""
Content Finder Module - AI Shorts Factory
Searches Pexels API (with fallback search) for licensed, high-quality portrait videos.
Returns structured JSON with optimal video candidate details.
"""

import os
import sys
import json
import argparse
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("content_finder")

PEXELS_API_URL = "https://api.pexels.com/videos/search"

def search_pexels(topic: str, per_page: int = 15) -> list:
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key or api_key.startswith("mock_"):
        logger.warning("PEXELS_API_KEY is missing or mock. Using fallback candidate provider.")
        return get_mock_candidates(topic)
    
    headers = {"Authorization": api_key}
    params = f"?query={topic}&orientation=portrait&per_page={per_page}"
    
    try:
        import urllib.request
        req = urllib.request.Request(PEXELS_API_URL + params, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("videos", [])
    except Exception as e:
        logger.error(f"Failed to query Pexels API: {e}")
        return get_mock_candidates(topic)
    
    return get_mock_candidates(topic)

def rank_and_select_video(videos: list) -> dict:
    if not videos:
        return None
    
    candidates = []
    for video in videos:
        duration = video.get("duration", 0)
        # Target duration 10 - 60 seconds
        if duration < 5 or duration > 60:
            continue
            
        video_files = video.get("video_files", [])
        best_file = None
        highest_res = 0
        
        for vf in video_files:
            width = vf.get("width", 0) or 0
            height = vf.get("height", 0) or 0
            if height > width: # Portrait preferred
                res = width * height
                if res > highest_res:
                    highest_res = res
                    best_file = vf
                    
        if not best_file and video_files:
            best_file = video_files[0]
            
        if best_file:
            score = highest_res + (100 - abs(30 - duration)) * 10
            candidates.append({
                "score": score,
                "video_id": video.get("id"),
                "video_url": best_file.get("link"),
                "duration": duration,
                "width": best_file.get("width", 1080),
                "height": best_file.get("height", 1920),
                "user": video.get("user", {}).get("name", "Unknown Creator")
            })
            
    if not candidates:
        # Fallback to first video raw details
        v = videos[0]
        v_files = v.get("video_files", [{}])
        vf = v_files[0] if v_files else {}
        return {
            "video_id": v.get("id", 101),
            "video_url": vf.get("link", "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4"),
            "duration": v.get("duration", 20),
            "width": vf.get("width", 1080),
            "height": vf.get("height", 1920),
            "user": "Fallback Creator"
        }
        
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[0]
    del selected["score"]
    return selected

def get_mock_candidates(topic: str) -> list:
    """Mock candidate video structure for testing and offline execution."""
    sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "sample.mp4"))
    return [
        {
            "id": 855280,
            "duration": 22,
            "user": {"name": "Nature Media"},
            "video_files": [
                {
                    "id": 1,
                    "quality": "hd",
                    "width": 1080,
                    "height": 1920,
                    "link": f"file://{sample_path}"
                }
            ]
        }
    ]

def main():
    parser = argparse.ArgumentParser(description="Find portrait videos for YouTube Shorts")
    parser.add_argument("--topic", type=str, default="waterfall", help="Topic / keyword to search for")
    args = parser.parse_args()
    
    logger.info(f"Searching content for topic: '{args.topic}'")
    videos = search_pexels(args.topic)
    best_candidate = rank_and_select_video(videos)
    
    if not best_candidate:
        logger.error("No valid video candidate found.")
        print(json.dumps({"status": "FAILED", "error": "No valid video candidate found"}))
        sys.exit(1)
        
    result = {
        "status": "SUCCESS",
        "topic": args.topic,
        "candidate": best_candidate
    }
    logger.info(f"Selected candidate video ID {best_candidate['video_id']} ({best_candidate['width']}x{best_candidate['height']}, {best_candidate['duration']}s)")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
