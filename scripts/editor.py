#!/usr/bin/env python3
"""
Editor Module - AI Shorts Factory
Runs ffmpeg/process_video.sh to turn a raw clip into a 1080x1920 YouTube Short.
If FFmpeg is missing or the edit fails, this reports FAILED: an unedited file is never passed on as a Short.
"""

import os
import sys
import time
import json
import shutil
import datetime
import argparse
import signal
import subprocess
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("editor")

EDIT_DIR = os.getenv("EDIT_PATH", "edited")
FFMPEG_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ffmpeg", "process_video.sh")


def _timeout_sec() -> int:
    """How long one edit may take, from FFMPEG_TIMEOUT_SEC (default 600)."""
    try:
        value = int(os.getenv("FFMPEG_TIMEOUT_SEC", "600"))
    except ValueError:
        value = 600
    return value if value > 0 else 600


def edit_video(input_path: str, output_path: str = None, duration: int = 30) -> dict:
    if not os.path.exists(input_path):
        return {"status": "FAILED", "error": f"Input file not found: {input_path}"}
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return {"status": "FAILED", "error": "FFmpeg is not installed. Install it, or run the pipeline in Docker."}

    if not output_path:
        os.makedirs(EDIT_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(EDIT_DIR, f"short_{timestamp}.mp4")

    start_time = time.time()
    logger.info(f"Editing video '{input_path}' -> '{output_path}'")
    timeout = _timeout_sec()
    # Own process group, so a timeout stops FFmpeg too and not just the wrapper script.
    proc = subprocess.Popen(
        ["bash", FFMPEG_SCRIPT, input_path, output_path, str(duration)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        if os.path.exists(output_path):
            os.remove(output_path)
        return {"status": "FAILED", "error": f"FFmpeg took longer than {timeout} seconds (raise FFMPEG_TIMEOUT_SEC on a slow machine)"}
    res = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)

    if res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        detail = (res.stderr or res.stdout or "").strip().splitlines()
        if os.path.exists(output_path):
            os.remove(output_path)
        return {"status": "FAILED", "error": f"FFmpeg edit failed: {detail[-1] if detail else 'no output produced'}"}

    edit_duration = time.time() - start_time
    file_size = os.path.getsize(output_path)
    logger.info(f"Video edited successfully in {edit_duration:.2f}s ({file_size} bytes)")
    return {
        "status": "SUCCESS",
        "file_path": output_path,
        "file_size_bytes": file_size,
        "duration_sec": duration,
        "edit_time_sec": round(edit_duration, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Edit raw video into YouTube Shorts format")
    parser.add_argument("--input", type=str, required=True, help="Input raw video path")
    parser.add_argument("--output", type=str, default=None, help="Output edited video path")
    parser.add_argument("--duration", type=int, default=30, help="Target duration in seconds")
    args = parser.parse_args()

    result = edit_video(args.input, args.output, args.duration)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
