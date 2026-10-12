#!/usr/bin/env python3
"""
Story Pipeline - AI Shorts Factory
Full AI commentary reels (attentioncompound style), end to end and free:
script -> voiceover -> word-timed captions -> several free stock clips cut
together with the deep-fried look -> channel logo -> upload to YouTube
(private first) and Instagram. Capped at MAX_DURATION_SECONDS (60s).
"""
import os
import sys
import json
import time
import logging
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_writer import write_script          # noqa: E402
from voiceover import make_voiceover            # noqa: E402
import captions                                 # noqa: E402
from content_finder import find_videos, mock_mode  # noqa: E402
from downloader import download_video           # noqa: E402
from validator import validate_video            # noqa: E402
from metadata_generator import generate_metadata  # noqa: E402
from archive import archive_processed_media     # noqa: E402

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("story_pipeline")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY_SCRIPT = os.path.join(ROOT, "ffmpeg", "process_story.sh")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")


def _collect_clips(topic: str, want: int) -> list:
    """Download up to `want` distinct free stock clips for the topic.
    In mock mode (or when the search comes up thin) the bundled sample video
    stands in so the reel still cuts together."""
    if mock_mode():
        sample = os.path.join(ROOT, "tests", "sample.mp4")
        if not os.path.exists(sample):
            return []
        clips = []
        for i in range(want):
            copy_path = sample + f".story{i}.mp4"
            import shutil
            shutil.copyfile(sample, copy_path)
            clips.append(copy_path)
        return clips
    clips = []
    from content_finder import _pick_file
    for cand in find_videos(topic):
        if len(clips) >= want:
            break
        url = cand.get("video_url")
        if not url and cand.get("video_files"):
            best_file, _ = _pick_file(cand.get("video_files", []))
            if best_file:
                url = best_file.get("link")
        if not url:
            continue
        dl = download_video(url)
        if dl.get("status") == "SUCCESS" and os.path.exists(dl.get("file_path", "")):
            clips.append(dl["file_path"])
    return clips


def produce_story(topic: str, duration: int = 45, logo: str = None, n_clips: int = 3, on_progress = None) -> dict:
    started = time.time()
    steps = {}
    raw_clips = edited_path = None
    workdir = tempfile.mkdtemp(prefix="story_")

    max_duration = int(os.getenv("MAX_DURATION_SECONDS", "60"))
    duration = max(10, min(duration, max_duration))
    logo = logo or os.getenv("LOGO_FILE") or ""
    n_clips = max(1, min(int(os.getenv("STORY_CLIPS", str(n_clips))), 5))

    def notify(step: str, status: str, detail: str = None):
        if callable(on_progress):
            try:
                on_progress(step, status, detail)
            except Exception:
                pass

    def fail(step: str, error: str) -> dict:
        logger.error("Story pipeline stopped at '%s': %s", step, error)
        notify(step, "failed", error)
        from run_pipeline import log_execution
        log_execution(topic, "FAILED", os.path.basename(edited_path or ""), "",
                      "", execution_time_sec=round(time.time() - started, 2), error_message=f"{step}: {error}")
        return {"status": "FAILED", "failed_step": step, "error": error, "steps": steps,
                "mode": "MOCK" if mock_mode() else "PRODUCTION"}

    if not mock_mode() and not (os.getenv("PEXELS_API_KEY") or os.getenv("PIXABAY_API_KEY")):
        return fail("find", "No video API key set. Add a free PEXELS_API_KEY or PIXABAY_API_KEY to .env, or set SHORTS_MOCK=1 for a test run.")

    notify("script", "running", topic)
    script = write_script(topic)
    steps["script"] = {"writer": script["writer"], "lines": len(script["lines"])}
    notify("script", "done")

    notify("voiceover", "running")
    vo = make_voiceover(script["lines"], workdir)
    steps["voiceover"] = {"voice": vo.get("voice"), "words": len(vo.get("words") or [])}
    if vo.get("status") != "SUCCESS":
        return fail("voiceover", vo.get("error", "voiceover failed"))
    notify("voiceover", "done")

    notify("captions", "running")
    ass_path = os.path.join(workdir, "captions.ass")
    has_captions = captions.build_ass(vo.get("words"), ass_path)
    if not has_captions:
        has_captions = captions.fallback_ass(script["lines"], 60.0, ass_path)
    steps["captions"] = "word-timed" if has_captions else "none"
    notify("captions", "done")

    notify("find", "running", f"{n_clips} clips for {topic}")
    raw_clips = _collect_clips(topic, n_clips)
    steps["clips"] = len(raw_clips)
    if len(raw_clips) < 1:
        return fail("find", "no usable stock clips for this topic")
    notify("find", "done")

    notify("edit", "running", f"story reel, {duration}s")
    edited_path = os.path.join(workdir, "story_reel.mp4")
    cmd = ["bash", STORY_SCRIPT, edited_path, str(duration), vo["file"]]
    if has_captions:
        cmd.append(ass_path)
    cmd.extend(raw_clips)
    env = dict(os.environ)
    if logo and os.path.exists(logo):
        env["LOGO_FILE"] = os.path.abspath(logo)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
    if proc.returncode != 0 or not os.path.exists(edited_path) or os.path.getsize(edited_path) == 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return fail("edit", detail[-1] if detail else "story edit produced no output")
    steps["edit"] = {"file": edited_path, "size": os.path.getsize(edited_path)}
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
        "style": "story",
        "mode_type": "story",
        "writer": script["writer"],
        "voice": vo.get("voice"),
        "duration": duration,
        "raw_path": raw_clips[0] if raw_clips else None,
        "raw_clips": raw_clips,
        "edited_path": edited_path,
        "file_path": edited_path,
        "metadata": meta,
        "total_time_sec": elapsed,
        "steps": steps,
    }


def run_story(topic: str, duration: int = 45, privacy: str = "private", keep_files: bool = False,
              logo: str = None, n_clips: int = 3, publish_at: str = None, on_progress = None) -> dict:
    started = time.time()
    prod = produce_story(topic, duration=duration, logo=logo, n_clips=n_clips, on_progress=on_progress)
    if prod.get("status") != "SUCCESS":
        return prod

    steps = prod.get("steps", {})
    edited_path = prod["edited_path"]
    meta = prod["metadata"]
    raw_clips = prod.get("raw_clips", [])

    from run_pipeline import publish_youtube_video, publish_instagram_video
    upload = publish_youtube_video(edited_path, title=meta["title"], description=meta["description"],
                                   tags=meta["tags"], privacy=privacy, publish_at=publish_at,
                                   on_progress=on_progress)
    steps["upload"] = upload
    if upload.get("status") != "SUCCESS":
        from run_pipeline import log_execution
        logger.error("Story upload failed: %s", upload.get("error"))
        log_execution(topic, "FAILED", os.path.basename(edited_path), "", "",
                      execution_time_sec=round(time.time() - started, 2),
                      error_message=f"upload: {upload.get('error')}")
        return {"status": "FAILED", "failed_step": "upload", "error": upload.get("error", "upload failed"),
                "steps": steps, "mode": "MOCK" if mock_mode() else "PRODUCTION"}

    ig = publish_instagram_video(edited_path, title=meta["title"], description=meta["description"],
                                 tags=meta["tags"], on_progress=on_progress)
    steps["upload_instagram"] = ig
    if ig.get("status") != "SUCCESS":
        logger.warning("Instagram post failed (YouTube is already up): %s", ig.get("error", ""))

    elapsed = round(time.time() - started, 2)
    from run_pipeline import log_execution
    log_execution(topic, "SUCCESS", os.path.basename(edited_path), upload["video_id"], upload["youtube_url"],
                  execution_time_sec=elapsed)
    if not keep_files and raw_clips:
        steps["archive"] = archive_processed_media(raw_clips[0], edited_path)

    return {"status": "SUCCESS", "mode": upload.get("mode"), "topic": topic, "style": "story",
            "writer": prod.get("writer"), "voice": prod.get("voice"), "youtube_url": upload["youtube_url"],
            "instagram": ig.get("status"), "instagram_url": ig.get("instagram_url", ""),
            "privacy": privacy, "total_time_sec": elapsed, "steps": steps}



def main():
    import argparse
    parser = argparse.ArgumentParser(description="Full AI commentary reel: script, voiceover, captions, clips, upload")
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--duration", type=int, default=45)
    parser.add_argument("--privacy", type=str, default="private")
    parser.add_argument("--keep-files", action="store_true")
    parser.add_argument("--logo", type=str, default=None)
    parser.add_argument("--clips", type=int, default=3)
    args = parser.parse_args()
    result = run_story(args.topic, duration=args.duration, privacy=args.privacy,
                       keep_files=args.keep_files, logo=args.logo, n_clips=args.clips)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
