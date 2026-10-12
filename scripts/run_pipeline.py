#!/usr/bin/env python3
"""
Run Pipeline - AI Shorts Factory
Runs every step for one Short in order, the same steps the n8n workflows chain:
find -> download -> validate -> edit (1080x1920) -> validate -> metadata -> upload -> log -> archive.

Real run (needs a free Pexels/Pixabay key and YouTube OAuth values in .env):
    python scripts/run_pipeline.py --topic "ocean waves"
Test run (no API calls, nothing uploaded, real FFmpeg rendering):
    SHORTS_MOCK=1 python scripts/run_pipeline.py --topic ocean
Uploads go up as private by default so you can check each Short before it goes public.
"""

import os
import sys
import json
import time
import argparse
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.archive import archive_processed_media
from scripts.content_finder import find_videos, rank_and_select_video, mock_mode, real_key
from scripts.downloader import download_video
from scripts.editor import edit_video
from scripts.logger import log_execution
from scripts.metadata_generator import generate_metadata
from scripts.uploader import upload_to_youtube
from scripts.instagram_uploader import upload_to_instagram
from scripts.validator import validate_video

logger = logging.getLogger("run_pipeline")


def produce(topic: str, duration: int = 30, style: str = None, logo: str = None,
            mode: str = "clip", on_progress = None) -> dict:
    started = time.time()
    steps = {}
    raw_path = edited_path = None
    max_duration = int(os.getenv("MAX_DURATION_SECONDS", "60"))
    duration = max(5, min(duration, max_duration))
    style = (style or os.getenv("EDIT_STYLE") or "cinematic").strip().lower()

    def notify(step: str, status: str, detail: str = None):
        if callable(on_progress):
            try:
                on_progress(step, status, detail)
            except Exception:
                pass

    def fail(step: str, error: str) -> dict:
        logger.error(f"Pipeline stopped at '{step}': {error}")
        notify(step, "failed", error)
        log_execution(topic, "FAILED", os.path.basename(edited_path or raw_path or ""),
                      execution_time_sec=round(time.time() - started, 2), error_message=f"{step}: {error}")
        return {"status": "FAILED", "failed_step": step, "error": error, "steps": steps,
                "mode": "MOCK" if mock_mode() else "PRODUCTION"}

    if mode == "story":
        from scripts.story_pipeline import produce_story
        return produce_story(topic, duration=duration, logo=logo, on_progress=on_progress)

    if not mock_mode() and not (real_key("PEXELS_API_KEY") or real_key("PIXABAY_API_KEY")):
        return fail("find", "No video API key set. Add a free PEXELS_API_KEY or PIXABAY_API_KEY to .env, or set SHORTS_MOCK=1 for a test run.")

    notify("find", "running", topic)
    candidate = rank_and_select_video(find_videos(topic))
    if not candidate:
        return fail("find", f"No usable video found for '{topic}'")
    steps["find"] = candidate
    notify("find", "done")

    notify("download", "running")
    download = download_video(candidate["video_url"])
    steps["download"] = download
    if download.get("status") != "SUCCESS":
        return fail("download", download.get("error", "download failed"))
    raw_path = download["file_path"]
    notify("download", "done")

    notify("validate_raw", "running")
    check = validate_video(raw_path)
    steps["validate_raw"] = check
    if check.get("status") != "PASS":
        return fail("validate_raw", check.get("reason", "invalid source video"))
    notify("validate_raw", "done")

    notify("edit", "running", f"{style}, {duration}s")
    edit = edit_video(raw_path, duration=duration, logo=logo, style=style, caption=topic)
    steps["edit"] = edit
    if edit.get("status") != "SUCCESS":
        return fail("edit", edit.get("error", "edit failed"))
    edited_path = edit["file_path"]
    notify("edit", "done")

    notify("validate_edited", "running")
    check = validate_video(edited_path)
    steps["validate_edited"] = check
    if check.get("status") != "PASS" or check.get("width") != 1080 or check.get("height") != 1920:
        return fail("validate_edited", check.get("reason") or f"edited video is {check.get('width')}x{check.get('height')}, expected 1080x1920")
    notify("validate_edited", "done")

    notify("metadata", "running")
    meta = generate_metadata(topic)
    steps["metadata"] = meta
    if meta.get("status") != "SUCCESS":
        return fail("metadata", meta.get("error", "metadata failed"))
    notify("metadata", "done")

    elapsed = round(time.time() - started, 2)
    return {
        "status": "SUCCESS",
        "mode": "MOCK" if mock_mode() else "PRODUCTION",
        "topic": topic,
        "style": style,
        "mode_type": mode,
        "duration": duration,
        "raw_path": raw_path,
        "edited_path": edited_path,
        "file_path": edited_path,
        "metadata": meta,
        "total_time_sec": elapsed,
        "steps": steps,
    }


def publish_youtube_video(file_path: str, title: str = "", description: str = "",
                          tags: list = None, privacy: str = "private",
                          publish_at: str = None, on_progress = None) -> dict:
    if callable(on_progress):
        try:
            status_label = f"YouTube ({privacy}, scheduled: {publish_at})" if publish_at else f"YouTube ({privacy})"
            on_progress("upload", "running", status_label)
        except Exception:
            pass
    upload = upload_to_youtube(file_path, title=title, description=description,
                               tags=tags or [], privacy_status=privacy, publish_at=publish_at)
    if callable(on_progress):
        try:
            on_progress("upload", "done" if upload.get("status") == "SUCCESS" else "failed")
        except Exception:
            pass
    return upload


def publish_instagram_video(file_path: str, caption: str = None, title: str = "",
                            description: str = "", tags: list = None, on_progress = None) -> dict:
    if callable(on_progress):
        try:
            on_progress("upload_instagram", "running", "Instagram Reel")
        except Exception:
            pass
    if not caption:
        caption = f"{title}\n\n{description}"
        if tags:
            caption = f"{caption}\n\n" + " ".join(f"#{t.replace(' ', '')}" for t in tags[:10])
    ig = upload_to_instagram(file_path, caption=caption)
    if callable(on_progress):
        try:
            on_progress("upload_instagram", "done" if ig.get("status") == "SUCCESS" else "failed")
        except Exception:
            pass
    return ig


def run(topic: str, duration: int = 30, privacy: str = "private", keep_files: bool = False,
        logo: str = None, style: str = None, publish_at: str = None, on_progress = None) -> dict:
    started = time.time()
    style = (style or os.getenv("EDIT_STYLE") or "cinematic").strip().lower()

    prod = produce(topic, duration=duration, style=style, logo=logo, mode="clip", on_progress=on_progress)
    if prod.get("status") != "SUCCESS":
        return prod

    steps = prod.get("steps", {})
    edited_path = prod["edited_path"]
    raw_path = prod["raw_path"]
    meta = prod["metadata"]

    deliverables_dir = os.path.join(ROOT, "deliverables")
    os.makedirs(deliverables_dir, exist_ok=True)
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30].strip("_")
    deliverable_video = os.path.join(deliverables_dir, f"short_{clean_topic}_{ts}.mp4")
    deliverable_meta = os.path.join(deliverables_dir, f"short_{clean_topic}_{ts}.json")
    import shutil
    shutil.copy2(edited_path, deliverable_video)
    with open(deliverable_meta, "w", encoding="utf-8") as f:
        json.dump({
            "topic": topic,
            "created_at": datetime.datetime.now().isoformat(),
            "metadata": meta,
            "duration": duration,
            "deliverable_video": deliverable_video,
            "privacy": privacy,
            "publish_at": publish_at,
        }, f, indent=2)

    upload = publish_youtube_video(edited_path, title=meta["title"], description=meta["description"],
                                   tags=meta["tags"], privacy=privacy, publish_at=publish_at,
                                   on_progress=on_progress)
    steps["upload"] = upload

    ig = publish_instagram_video(edited_path, title=meta["title"], description=meta["description"],
                                 tags=meta["tags"], on_progress=on_progress)
    steps["upload_instagram"] = ig
    if ig.get("status") != "SUCCESS":
        logger.warning("Instagram post failed: %s", ig.get("error", ""))

    if upload.get("status") == "QUOTA_EXCEEDED":
        elapsed = round(time.time() - started, 2)
        logger.warning("YouTube quota exceeded. Short preserved in deliverables/: %s", deliverable_video)
        log_execution(topic, "SUCCESS_LOCAL", os.path.basename(deliverable_video), "", "",
                      execution_time_sec=elapsed)
        return {"status": "SUCCESS", "mode": "LOCAL_QUEUE", "topic": topic, "style": style,
                "youtube_url": "", "deliverable_file": deliverable_video,
                "instagram": ig.get("status"), "instagram_url": ig.get("instagram_url", ""),
                "queue_reason": "YouTube daily quota reached", "privacy": privacy,
                "total_time_sec": elapsed, "steps": steps}

    if upload.get("status") != "SUCCESS":
        logger.error(f"Pipeline stopped at 'upload': {upload.get('error')}")
        log_status = "SUCCESS" if ig.get("status") == "SUCCESS" else "FAILED"
        log_execution(topic, log_status, os.path.basename(edited_path),
                      execution_time_sec=round(time.time() - started, 2),
                      error_message=f"upload: {upload.get('error')}")
        if ig.get("status") == "SUCCESS":
            return {"status": "SUCCESS", "mode": "PRODUCTION", "topic": topic,
                    "youtube_url": "", "deliverable_file": deliverable_video,
                    "instagram": ig.get("status"), "instagram_url": ig.get("instagram_url", ""),
                    "style": style, "privacy": privacy, "total_time_sec": round(time.time() - started, 2), "steps": steps}
        return {"status": "FAILED", "failed_step": "upload", "error": upload.get("error", "upload failed"),
                "deliverable_file": deliverable_video,
                "steps": steps, "mode": "MOCK" if mock_mode() else "PRODUCTION"}

    elapsed = round(time.time() - started, 2)
    log_execution(topic, "SUCCESS", os.path.basename(edited_path), upload["video_id"], upload["youtube_url"],
                  execution_time_sec=elapsed)
    if not keep_files:
        steps["archive"] = archive_processed_media(raw_path, edited_path)

    return {"status": "SUCCESS", "mode": upload.get("mode"), "topic": topic, "youtube_url": upload["youtube_url"],
            "deliverable_file": deliverable_video,
            "instagram": ig.get("status"), "instagram_url": ig.get("instagram_url", ""),
            "style": style, "privacy": privacy, "total_time_sec": elapsed, "steps": steps}



def main():
    parser = argparse.ArgumentParser(description="Make and upload one YouTube Short")
    parser.add_argument("--topic", default="waterfall", help="What the Short is about, e.g. 'ocean waves'")
    parser.add_argument("--duration", type=int, default=30, help="Target length in seconds (max 180)")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--keep-files", action="store_true", help="Leave the raw and edited files in place instead of archiving them")
    parser.add_argument("--style", choices=["cinematic", "brainrot"], help="Editing style (default: EDIT_STYLE or cinematic)")
    parser.add_argument("--mode", choices=["clip", "story"], default=None, help="clip = stock clip + effects; story = full AI commentary reel (script, voiceover, word-timed captions, multi-clip cuts)")
    args = parser.parse_args()
    if not 5 <= args.duration <= 180:
        parser.error("--duration must be between 5 and 180 seconds")
    mode = args.mode or os.getenv("STORY_MODE", "").strip().lower() or "clip"

    if mode == "story":
        from story_pipeline import run_story
        result = run_story(args.topic, duration=args.duration, privacy=args.privacy,
                           keep_files=args.keep_files, logo=os.getenv("LOGO_FILE"))
    else:
        result = run(args.topic, args.duration, args.privacy, args.keep_files, style=args.style)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
