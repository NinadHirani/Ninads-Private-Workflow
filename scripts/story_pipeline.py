#!/usr/bin/env python3
"""
Story Pipeline - AI Shorts Factory
Full AI commentary reels with creative variety, end to end:
1. Smart Topic & Genre Detection (Anime, Gaming, Sci-Fi Lore, Mystery Facts, Nature)
2. High-Retention Script & Edge-TTS Neural Voiceover
3. Hybrid Visuals: Free 1080x1920 AI scene art (Pollinations Flux/Anime) or stock clips
4. Programmatic Video Rendering with Remotion (dynamic captions, Ken Burns pan/zoom, styling)
5. Direct autonomous upload to YouTube & Instagram
"""
import os
import sys
import json
import time
import datetime
import logging
import tempfile
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_writer import write_script
from voiceover import make_voiceover
from scene_generator import classify_topic, collect_scenes
from remotion_renderer import render_with_remotion
from content_finder import mock_mode
from validator import validate_video
from metadata_generator import generate_metadata
from archive import archive_processed_media, delete_processed_media
from logger import mark_asset_used, mark_topic_used, log_execution

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("story_pipeline")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORY_SCRIPT = os.path.join(ROOT, "ffmpeg", "process_story.sh")


def _convert_image_scene_to_clip(image_path: str, out_path: str, duration_sec: float, fps: int = 30):
    """Converts a still AI image scene into a short video clip.

    The FFmpeg fallback assembler (process_story.sh) consumes video clips only,
    so still image scenes must be looped into real clips here. Without this the
    fallback silently drops the AI-generated visuals and substitutes stock
    sample footage."""
    if not image_path or not os.path.exists(image_path):
        return None
    duration = max(float(duration_sec or 0.0), 1.0)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{duration:.2f}",
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", out_path,
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except Exception as exc:
        logger.warning("Image scene conversion failed for %s: %s", image_path, exc)
        return None
    if proc.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        logger.warning("Image scene conversion produced no clip for %s", image_path)
        return None
    return out_path


def _fallback_clip_paths(scenes: list, workdir: str, fps: int = 30):
    """Builds the FFmpeg fallback clip list in scene order.

    Video scenes pass through unchanged; image scenes are converted to clips so
    AI-generated visuals survive a Remotion failure. tests/sample.mp4 is used
    only when nothing else could be assembled."""
    clips = []
    for idx, sc in enumerate(scenes):
        src = sc.get("src") or ""
        if sc.get("type") == "video":
            if src and os.path.exists(src):
                clips.append(src)
            continue
        frames = sc.get("durationInFrames") or 0
        out_path = os.path.join(workdir, f"fallback_scene_{idx}.mp4")
        clip = _convert_image_scene_to_clip(src, out_path, frames / float(fps), fps=fps)
        if clip:
            clips.append(clip)
    if not clips:
        clips = [os.path.join(ROOT, "tests", "sample.mp4")]
    return clips


def produce_story(topic: str, duration: int = 45, logo: str = None, n_clips: int = 4, on_progress = None) -> dict:
    started = time.time()
    steps = {}
    workdir = tempfile.mkdtemp(prefix="story_")

    max_duration = int(os.getenv("MAX_DURATION_SECONDS", "60"))
    duration = max(10, min(duration, max_duration))
    logo = logo or os.getenv("LOGO_FILE") or ""

    def notify(step: str, status: str, detail: str = None):
        if callable(on_progress):
            try:
                on_progress(step, status, detail)
            except Exception:
                pass

    def fail(step: str, error: str) -> dict:
        logger.error("Story pipeline stopped at '%s': %s", step, error)
        notify(step, "failed", error)
        log_execution(topic, "FAILED", "", "", "",
                      execution_time_sec=round(time.time() - started, 2), error_message=f"{step}: {error}")
        return {"status": "FAILED", "failed_step": step, "error": error, "steps": steps,
                "mode": "MOCK" if mock_mode() else "PRODUCTION"}

    # 1. Classify Topic & Genre
    notify("classify", "running", topic)
    genre_info = classify_topic(topic)
    steps["classify"] = genre_info
    notify("classify", "done", f"Genre: {genre_info['category']}, Style: {genre_info['style']}")

    # 2. Audio & Speech Configuration (Context-Aware: Original Scene Voice vs Nature vs Commentary)
    from scripts.sound_manager import get_audio_assets_for_topic
    audio_override = os.getenv("AUDIO_MODE")
    audio_cfg = get_audio_assets_for_topic(
        topic,
        genre_info["category"],
        genre_info.get("music_mood", "calm_ambient"),
        duration=int(duration),
        override_mode=audio_override
    )

    if audio_cfg["mode"] == "original_voice":
        # Anime & Movie Scenes: Preserve original character dialogue & scene audio, NO AI speech
        script = {"lines": [], "writer": "original_voice"}
        vo = {"status": "SUCCESS", "file": None, "words": []}
        words = []
        final_duration = float(duration)
        steps["audio_mode"] = "original_voice"
        steps["voiceover"] = {"voice": None, "words": 0, "mode": "original_voice"}
        notify("voiceover", "done", "Original Voice mode: scene character audio & original sound preserved")
    elif audio_cfg["mode"] == "nature_asmr":
        # Nature & Pure ASMR: Realistic natural soundscape + calming music, NO AI speech
        script = {"lines": [], "writer": "nature_soundscape"}
        vo = {"status": "SUCCESS", "file": None, "words": []}
        words = []
        final_duration = float(duration)
        steps["audio_mode"] = "nature_asmr"
        steps["voiceover"] = {"voice": None, "words": 0, "mode": "nature_asmr"}
        notify("voiceover", "done", "Nature ASMR mode: natural soundscape + relaxing ambient music")
    else:
        # Commentary (Facts, Stoic, Tech, etc.): high-retention viral script + neural voiceover
        notify("script", "running", topic)
        script = write_script(topic, category=genre_info["category"])
        steps["script"] = {"writer": script["writer"], "lines": len(script["lines"]), "category": genre_info["category"]}
        notify("script", "done")

        notify("voiceover", "running")
        vo = make_voiceover(script["lines"], workdir)
        steps["voiceover"] = {"voice": vo.get("voice"), "words": len(vo.get("words") or [])}
        if vo.get("status") != "SUCCESS":
            return fail("voiceover", vo.get("error", "voiceover failed"))
        notify("voiceover", "done")

        words = vo.get("words") or []
        if words:
            last_item = words[-1]
            if isinstance(last_item, dict):
                last_end = float(last_item.get("end", duration))
            elif isinstance(last_item, (list, tuple)) and len(last_item) >= 3:
                last_end = float(last_item[2])
            else:
                last_end = float(duration)
            spoken_duration = max(last_end, 8.0) + 1.0
            final_duration = min(spoken_duration, float(max_duration))
        else:
            final_duration = float(duration)

    # 4. Hybrid Scene Generation (AI Scenes or Stock Video)
    notify("scenes", "running", f"{genre_info['visual_mode']} for {topic}")
    scenes = collect_scenes(topic, final_duration, workdir, n_scenes=n_clips, on_progress=notify)
    steps["scenes"] = len(scenes)
    if not scenes:
        return fail("scenes", "could not generate or collect visual scenes for this topic")
    notify("scenes", "done")

    # 5. Render with Remotion (programmatic 1080x1920 video with kinetic captions & Ken Burns motion)
    notify("edit", "running", f"Remotion render ({genre_info['style']}, {round(final_duration, 1)}s)")
    edited_path = os.path.join(workdir, "remotion_short.mp4")

    remotion_res = render_with_remotion(
        scenes=scenes,
        voiceover_wav=vo.get("file"),
        words=words,
        output_mp4=edited_path,
        title=genre_info.get("badge_title", topic.upper()[:40]),
        style=genre_info.get("style", "cinematic"),
        music_src=audio_cfg.get("music_src"),
        music_volume=audio_cfg.get("music_volume", 0.18),
        ambient_src=audio_cfg.get("ambient_src"),
        ambient_volume=audio_cfg.get("ambient_volume", 0.65),
        logo_src=logo if logo and os.path.exists(logo) else None,
        fallback_text=" ".join(script.get("lines", [])),
        use_original_audio=audio_cfg.get("use_original_audio", False),
        on_progress=notify,
    )

    engine_used = "remotion"
    if remotion_res.get("status") != "SUCCESS" or not os.path.exists(edited_path):
        # Fallback to ffmpeg process_story.sh if Remotion encounters an unexpected issue
        logger.warning("Remotion render failed (%s), falling back to FFmpeg process_story.sh", remotion_res.get("error"))
        import captions
        ass_path = os.path.join(workdir, "captions.ass")
        has_captions = captions.build_ass(words, ass_path) or captions.fallback_ass(script["lines"], 60.0, ass_path)
        raw_clip_paths = _fallback_clip_paths(scenes, workdir)
        video_srcs = [s["src"] for s in scenes if s["type"] == "video"]
        fallback_audio = vo.get("file") or audio_cfg.get("ambient_src") or audio_cfg.get("music_src")
        if not fallback_audio or not os.path.exists(fallback_audio):
            if audio_cfg.get("use_original_audio") and video_srcs and os.path.exists(video_srcs[0]):
                fallback_audio = video_srcs[0]
            else:
                fallback_audio = os.path.join(workdir, "silence.wav")
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(int(final_duration)), fallback_audio],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = ["bash", STORY_SCRIPT, edited_path, str(int(final_duration)), fallback_audio]
        if has_captions:
            cmd.append(ass_path)
        cmd.extend(raw_clip_paths)
        env = dict(os.environ)
        if logo and os.path.exists(logo):
            env["LOGO_FILE"] = os.path.abspath(logo)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
        if proc.returncode != 0 or not os.path.exists(edited_path) or os.path.getsize(edited_path) == 0:
            return fail("edit", f"Both Remotion and FFmpeg render failed: {remotion_res.get('error')}")
        engine_used = "ffmpeg_fallback"

    steps["edit"] = {"file": edited_path, "size": os.path.getsize(edited_path), "engine": engine_used}
    notify("edit", "done")

    # 6. Validate Output Video
    notify("validate_edited", "running")
    check = validate_video(edited_path)
    steps["validate_edited"] = check
    if check.get("status") != "PASS" or check.get("width") != 1080 or check.get("height") != 1920:
        return fail("validate_edited", check.get("reason") or f"edited video is {check.get('width')}x{check.get('height')}, expected 1080x1920")
    notify("validate_edited", "done")

    # 7. Generate Rich Metadata (Title, Description, Tags)
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
        "style": genre_info["style"],
        "category": genre_info["category"],
        "mode_type": "story",
        "writer": script["writer"],
        "voice": vo.get("voice"),
        "duration": round(final_duration, 1),
        "raw_path": scenes[0]["src"] if scenes else None,
        "scenes": scenes,
        "workdir": workdir,
        "edited_path": edited_path,
        "file_path": edited_path,
        "metadata": meta,
        "total_time_sec": elapsed,
        "steps": steps,
    }


def run_story(topic: str, duration: int = 45, privacy: str = "private", keep_files: bool = False,
              logo: str = None, n_clips: int = 4, publish_at: str = None, on_progress = None,
              upload: bool = True) -> dict:
    started = time.time()
    prod = produce_story(topic, duration=duration, logo=logo, n_clips=n_clips, on_progress=on_progress)
    if prod.get("status") != "SUCCESS":
        return prod

    steps = prod.get("steps", {})
    edited_path = prod["edited_path"]
    meta = prod["metadata"]

    deliverables_dir = os.path.join(ROOT, "deliverables")
    os.makedirs(deliverables_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30].strip("_")
    deliverable_video = os.path.join(deliverables_dir, f"short_{clean_topic}_{ts}.mp4")
    deliverable_meta = os.path.join(deliverables_dir, f"short_{clean_topic}_{ts}.json")

    shutil.copy2(edited_path, deliverable_video)
    with open(deliverable_meta, "w", encoding="utf-8") as f:
        json.dump({
            "topic": topic,
            "created_at": datetime.datetime.now().isoformat(),
            "metadata": meta,
            "category": prod.get("category"),
            "style": prod.get("style"),
            "duration": prod.get("duration"),
            "deliverable_video": deliverable_video,
            "privacy": privacy,
            "publish_at": publish_at,
        }, f, indent=2)

    workdir = prod.get("workdir")
    stock_clip_files = [s["src"] for s in prod.get("scenes", []) if s.get("type") == "video" and str(s.get("src", "")).startswith(os.path.join(ROOT, "downloads"))]

    if not upload:
        elapsed = round(time.time() - started, 2)
        log_execution(topic, "SUCCESS_LOCAL", os.path.basename(deliverable_video), "", "",
                      execution_time_sec=elapsed)
        if not keep_files:
            delete_processed_media(edited_path=edited_path, workdir=workdir, extra_files=stock_clip_files)
        return {
            "status": "SUCCESS", "mode": "LOCAL", "topic": topic, "style": prod.get("style"),
            "category": prod.get("category"),
            "writer": prod.get("writer"), "voice": prod.get("voice"), "youtube_url": "",
            "deliverable_file": deliverable_video, "privacy": privacy,
            "total_time_sec": elapsed, "steps": steps
        }

    try:
        from scripts.run_pipeline import publish_youtube_video, publish_instagram_video
    except ImportError:
        from run_pipeline import publish_youtube_video, publish_instagram_video
    yt_upload = publish_youtube_video(edited_path, title=meta["title"], description=meta["description"],
                                      tags=meta["tags"], privacy=privacy, publish_at=publish_at,
                                      on_progress=on_progress)
    steps["upload"] = yt_upload

    # Strict Dual-or-None: If YouTube quota is reached or upload fails, DO NOT publish to Instagram yet.
    # Preserve both together in queue so they can be published simultaneously.
    if yt_upload.get("status") != "SUCCESS":
        queue_reason = "YouTube daily quota reached" if yt_upload.get("status") == "QUOTA_EXCEEDED" else yt_upload.get("error", "YouTube upload failed")
        from scripts.uploader import enqueue_dual_upload
        enqueue_dual_upload(deliverable_video, deliverable_meta, reason=queue_reason)
        elapsed = round(time.time() - started, 2)
        logger.warning("YouTube blocked (%s). STRICT DUAL-OR-NONE active: Instagram held back. Deliverable preserved in: %s",
                       queue_reason, deliverable_video)
        log_execution(topic, "SUCCESS_LOCAL", os.path.basename(deliverable_video), "", "",
                      execution_time_sec=elapsed)
        if not keep_files:
            delete_processed_media(edited_path=edited_path, workdir=workdir, extra_files=stock_clip_files)
        return {
            "status": "SUCCESS", "mode": "LOCAL_QUEUE", "topic": topic, "style": prod.get("style"),
            "category": prod.get("category"),
            "writer": prod.get("writer"), "voice": prod.get("voice"), "youtube_url": "",
            "deliverable_file": deliverable_video, "queue_reason": queue_reason,
            "instagram": "HOLD_FOR_YOUTUBE_SYNC", "instagram_url": "",
            "privacy": privacy, "total_time_sec": elapsed, "steps": steps
        }

    # YouTube upload succeeded! Now publish the exact same video to Instagram in lockstep.
    ig = publish_instagram_video(edited_path, title=meta["title"], description=meta["description"],
                                 tags=meta["tags"], on_progress=on_progress)
    steps["upload_instagram"] = ig
    if ig.get("status") != "SUCCESS":
        logger.warning("Instagram post failed after YouTube succeeded: %s", ig.get("error", ""))

    # Both platforms published in lockstep!
    elapsed = round(time.time() - started, 2)
    log_execution(topic, "SUCCESS", os.path.basename(edited_path), yt_upload["video_id"], yt_upload["youtube_url"],
                  execution_time_sec=elapsed)

    # Mark topic and assets as used to prevent repetition
    mark_topic_used(topic)
    for s in prod.get("scenes", []):
        if s.get("asset_id"):
            mark_asset_used(str(s["asset_id"]), provider="stock", topic=topic)
        if s.get("asset_url"):
            mark_asset_used(str(s["asset_url"]), provider="stock", topic=topic)

    if not keep_files:
        steps["cleanup"] = delete_processed_media(
            edited_path=edited_path,
            deliverable_video=deliverable_video,
            deliverable_meta=deliverable_meta,
            workdir=workdir,
            extra_files=stock_clip_files
        )

    return {
        "status": "SUCCESS", "mode": yt_upload.get("mode"), "topic": topic, "style": prod.get("style"),
        "category": prod.get("category"),
        "writer": prod.get("writer"), "voice": prod.get("voice"), "youtube_url": yt_upload["youtube_url"],
        "deliverable_file": deliverable_video,
        "instagram": ig.get("status"), "instagram_url": ig.get("instagram_url", ""),
        "privacy": privacy, "total_time_sec": elapsed, "steps": steps
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Full AI commentary reel: script, voiceover, Remotion render, upload")
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--duration", type=int, default=45)
    parser.add_argument("--privacy", type=str, default="private")
    parser.add_argument("--keep-files", action="store_true")
    parser.add_argument("--no-upload", action="store_true", help="Generate locally into deliverables/ without uploading")
    parser.add_argument("--logo", type=str, default=None)
    parser.add_argument("--clips", type=int, default=4)
    args = parser.parse_args()
    result = run_story(args.topic, duration=args.duration, privacy=args.privacy,
                       keep_files=args.keep_files, logo=args.logo, n_clips=args.clips,
                       upload=not args.no_upload)
    print(json.dumps(result, indent=2))
    if result["status"] != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
