#!/usr/bin/env python3
"""
Validator Module - AI Shorts Factory
Checks a raw video with ffprobe: it exists, is big enough, is playable, has a video stream,
a readable duration within range, and real dimensions. Anything ffprobe can't read fails.
"""

import os
import sys
import json
import argparse
import subprocess
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("validator")

MIN_SIZE_BYTES = 100 * 1024
MIN_DURATION = 5
MAX_DURATION = 180  # YouTube accepts Shorts up to 3 minutes; the editor trims to the target length


def validate_video(file_path: str, min_duration: float = MIN_DURATION, max_duration: float = MAX_DURATION) -> dict:
    if not os.path.exists(file_path):
        return {"status": "FAIL", "reason": f"File does not exist: {file_path}"}

    file_size = os.path.getsize(file_path)
    if file_size < MIN_SIZE_BYTES:
        return {"status": "FAIL", "reason": f"File size too small ({file_size} bytes)"}

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
        "-of", "json",
        file_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return {"status": "FAIL", "reason": "ffprobe is not installed, so the video can't be checked. Install FFmpeg (the Docker images include it)."}
    except subprocess.TimeoutExpired:
        return {"status": "FAIL", "reason": "ffprobe timed out reading the file"}

    if res.returncode != 0:
        detail = (res.stderr or "").strip().splitlines()
        return {"status": "FAIL", "reason": f"Not a playable video: {detail[-1] if detail else 'ffprobe could not read it'}"}

    try:
        info = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return {"status": "FAIL", "reason": "ffprobe returned unreadable output"}

    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        return {"status": "FAIL", "reason": "No video stream found"}
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if not width or not height:
        return {"status": "FAIL", "reason": "Could not read the video dimensions"}

    try:
        duration = float(info.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        return {"status": "FAIL", "reason": "Could not read the video duration"}
    if duration < min_duration or duration > max_duration:
        return {"status": "FAIL", "reason": f"Invalid video duration: {duration:.1f}s (allowed {min_duration}-{max_duration}s)"}

    codec = video.get("codec_name", "unknown")
    logger.info(f"FFprobe details: {width}x{height}, duration: {duration:.1f}s, codec: {codec}, audio: {has_audio}")
    return {
        "status": "PASS",
        "width": width,
        "height": height,
        "orientation": "portrait" if height > width else "landscape" if width > height else "square",
        "duration_sec": round(duration, 2),
        "codec": codec,
        "has_audio": has_audio,
        "file_size_bytes": file_size,
    }


def main():
    parser = argparse.ArgumentParser(description="Validate video file for AI Shorts Factory")
    parser.add_argument("--file", type=str, required=True, help="Path to raw video file")
    args = parser.parse_args()

    result = validate_video(args.file)
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
