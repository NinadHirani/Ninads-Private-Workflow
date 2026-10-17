#!/usr/bin/env python3
"""
Series Pipeline - AI Shorts Factory
Produces continuous episodic series videos using Remotion:
1. Persistent campaign state tracking (character condition, gear, era progression, cliffhangers)
2. Continuity-aware episodic script generation (resolving previous cliffhanger, setting up next)
3. Photorealistic AI scene generation with character visual anchors (Pollinations Flux / 35mm film still)
4. Gritty docu-narrator voiceover via Edge-TTS neural audio with word-level kinetic captions
5. Programmatic Remotion rendering with cinematic serial overlays (Episode badge, Era card, Cliffhanger CTA)
6. Multi-part batch season generation back-to-back
"""

import os
import sys
import json
import time
import shutil
import logging
import tempfile
import argparse
import subprocess
from typing import Dict, Any, Optional, List

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("series_pipeline")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.series_manager import (
    load_series,
    init_series,
    save_series,
    format_continuity_context,
    advance_series,
    get_current_era,
    list_all_series,
    DEFAULT_PRESETS,
)
from scripts.series_writer import write_series_episode
from scripts.voiceover import make_voiceover
from scripts.scene_generator import download_pollinations_image
from scripts.remotion_renderer import render_with_remotion
from scripts.content_finder import mock_mode
from scripts.validator import validate_video

try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text


def _get_audio_duration_sec(audio_file: str) -> float:
    """Probes audio file for duration using ffprobe, fallback to estimate."""
    if not audio_file or not os.path.exists(audio_file):
        return 30.0
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_file
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10)
        return max(5.0, float(out.decode().strip()))
    except Exception:
        # Fallback based on file size for 44.1kHz 16-bit stereo wav
        size = os.path.getsize(audio_file)
        return max(10.0, min(90.0, size / 176400.0))


def produce_episode(
    series_id: str = "kane",
    preset: str = "kane",
    target_duration: int = 40,
    on_progress = None
) -> Dict[str, Any]:
    """
    Produces a single continuous episode, maintaining unbroken continuity
    with all previous episodes and updating series state.
    """
    started = time.time()
    workdir = tempfile.mkdtemp(prefix=f"series_{series_id}_")

    def notify(step: str, status: str, detail: str = None):
        if callable(on_progress):
            try:
                on_progress(step, status, detail)
            except Exception:
                pass

    try:
        # 1. Load or Initialize Series
        notify("state", "running", f"Loading series '{series_id}'")
        state = load_series(series_id)
        if not state:
            state = init_series(series_id, preset=preset)
        ctx = format_continuity_context(state)
        ep_num = ctx["episode_number"]
        day_num = ctx["timeline_day"]
        notify("state", "done", f"Episode #{ep_num} • Day {day_num} • {ctx['era_name']}")

        # 2. Write Continuity Script & Visual Prompts
        notify("script", "running", f"Writing script for Episode #{ep_num}")
        episode_data = write_series_episode(ctx, target_duration=target_duration)
        notify("script", "done", f"'{episode_data.get('title')}' via {episode_data.get('writer', 'ai')}")

        # 3. Voiceover & Word Timings
        voice = state.get("voice", "en-US-ChristopherNeural")
        notify("voiceover", "running", f"Recording voiceover with {voice}")
        vo_res = make_voiceover(episode_data["script_lines"], workdir, voice=voice)
        if vo_res.get("status") != "SUCCESS":
            raise RuntimeError(f"Voiceover generation failed: {vo_res.get('error')}")
        vo_wav = vo_res.get("file")
        words = vo_res.get("words", [])
        total_audio_sec = _get_audio_duration_sec(vo_wav)
        notify("voiceover", "done", f"Audio duration: {total_audio_sec:.1f}s, {len(words)} words")

        # 4. Generate Visual Scenes with Character Anchors
        notify("visuals", "running", f"Generating photorealistic scenes for {ctx['character_name']}")
        prompts = episode_data.get("scene_prompts", [])
        fps = 30
        total_frames = int(max(15.0, total_audio_sec + 2.5) * fps)
        n_scenes = max(1, len(prompts))
        frames_per_scene = total_frames // n_scenes
        remainder_frames = total_frames - (frames_per_scene * n_scenes)

        scenes = []
        is_mock = mock_mode()

        for idx, p in enumerate(prompts):
            img_path = os.path.join(workdir, f"scene_{idx}.jpg")
            dur = frames_per_scene + (remainder_frames if idx == n_scenes - 1 else 0)

            if is_mock:
                sample_mp4 = os.path.join(ROOT, "tests", "sample.mp4")
                scenes.append({
                    "type": "video" if os.path.exists(sample_mp4) else "image",
                    "src": sample_mp4 if os.path.exists(sample_mp4) else img_path,
                    "durationInFrames": dur,
                })
                continue

            # In production: download photorealistic scene from Pollinations
            success = download_pollinations_image(p, img_path)
            if success and os.path.exists(img_path) and os.path.getsize(img_path) > 1000:
                scenes.append({
                    "type": "image",
                    "src": img_path,
                    "durationInFrames": dur,
                })
            else:
                logger.warning("Could not download scene %d, using local sample fallback", idx)
                sample_mp4 = os.path.join(ROOT, "tests", "sample.mp4")
                scenes.append({
                    "type": "video" if os.path.exists(sample_mp4) else "image",
                    "src": sample_mp4,
                    "durationInFrames": dur,
                })

        notify("visuals", "done", f"Assembled {len(scenes)} scenes")

        # 5. Programmatic Remotion Video Render
        notify("render", "running", "Rendering video with Remotion...")
        ts = time.strftime("%Y%m%d_%H%M%S")
        deliv_dir = os.path.join(ROOT, "deliverables")
        os.makedirs(deliv_dir, exist_ok=True)
        out_mp4 = os.path.join(deliv_dir, f"series_{series_id}_ep{ep_num:03d}_{ts}.mp4")

        # Serial Overlays
        ep_badge = f"EPISODE {ep_num:02d} • DAY {day_num}"
        ch_sub = f"{ctx['era_name']} • {episode_data.get('title')}".upper()
        next_cta = f"PART {ep_num + 1} DROPS TOMORROW • SUBSCRIBE"

        render_res = render_with_remotion(
            scenes=scenes,
            voiceover_wav=vo_wav,
            words=words,
            output_mp4=out_mp4,
            title=episode_data.get("title", f"Episode {ep_num}"),
            episode_badge=ep_badge,
            chapter_subtitle=ch_sub,
            cliffhanger_cta=next_cta,
            style=state.get("style", "cinematic"),
            fallback_text=" ".join(episode_data.get("script_lines", [])),
            show_captions=True,
            on_progress=notify,
        )

        if render_res.get("status") != "SUCCESS":
            raise RuntimeError(f"Remotion render failed: {render_res.get('error', 'unknown error')}")

        # 6. Validate Deliverable
        val = validate_video(out_mp4)
        if not val.get("valid"):
            logger.warning("Validation note for episode video: %s", val.get("reason"))

        # 7. Advance Series State (Persistent Campaign Update)
        episode_summary = {
            "title": episode_data.get("title"),
            "summary": episode_data.get("summary"),
            "cliffhanger": episode_data.get("cliffhanger"),
            "days_passed": episode_data.get("days_passed", 1),
            "new_location": episode_data.get("new_location"),
            "new_wounds": episode_data.get("new_wounds"),
            "new_gear": episode_data.get("new_gear"),
            "video_file": out_mp4,
        }
        updated_state = advance_series(series_id, episode_summary)
        notify("state", "done", f"Advanced series state to Episode #{updated_state['current_episode']}")

        # 8. Save Episode Metadata JSON
        meta_json = out_mp4.replace(".mp4", ".json")
        meta_data = {
            "series_id": series_id,
            "series_title": state.get("title"),
            "episode": ep_num,
            "timeline_day": day_num,
            "era": ctx["era_name"],
            "title": episode_data.get("title"),
            "summary": episode_data.get("summary"),
            "cliffhanger": episode_data.get("cliffhanger"),
            "script_lines": episode_data.get("script_lines"),
            "video_path": out_mp4,
            "duration_sec": render_res.get("duration_sec", total_audio_sec),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(meta_json, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)

        total_elapsed = round(time.time() - started, 2)
        logger.info("Successfully produced Episode #%d for series '%s' in %.1fs -> %s",
                    ep_num, series_id, total_elapsed, out_mp4)

        return {
            "status": "SUCCESS",
            "series_id": series_id,
            "episode": ep_num,
            "timeline_day": day_num,
            "title": episode_data.get("title"),
            "summary": episode_data.get("summary"),
            "cliffhanger": episode_data.get("cliffhanger"),
            "video_file": out_mp4,
            "metadata_file": meta_json,
            "duration_sec": render_res.get("duration_sec"),
            "elapsed_sec": total_elapsed,
        }

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def produce_batch(
    series_id: str = "kane",
    preset: str = "kane",
    count: int = 3,
    target_duration: int = 40,
    on_progress = None
) -> List[Dict[str, Any]]:
    """
    Generates multiple continuous episodes back-to-back in an unbroken narrative chain.
    """
    results = []
    logger.info("Starting Batch Season Generation: %d continuous episodes for '%s'", count, series_id)

    for i in range(count):
        logger.info("=== Producing Season Episode %d of %d ===", i + 1, count)
        res = produce_episode(
            series_id=series_id,
            preset=preset,
            target_duration=target_duration,
            on_progress=on_progress
        )
        results.append(res)
        if res.get("status") != "SUCCESS":
            logger.error("Batch aborted due to failure at episode %d: %s", i + 1, res.get("error"))
            break
        # Brief pause between episodes
        time.sleep(1.0)

    return results


def main():
    parser = argparse.ArgumentParser(description="Continuous Episodic Series Video Engine")
    parser.add_argument("--series", type=str, default="kane", help="Unique series ID (e.g., kane, goliath, zero_stickman)")
    parser.add_argument("--preset", type=str, default="kane", choices=list(DEFAULT_PRESETS.keys()), help="Initial template preset")
    parser.add_argument("--init", action="store_true", help="Initialize series state without producing video")
    parser.add_argument("--next", action="store_true", help="Produce the next single episode in sequence")
    parser.add_argument("--batch", type=int, default=0, help="Generate N continuous episodes in batch")
    parser.add_argument("--status", action="store_true", help="Show current state and history of the series")
    parser.add_argument("--list", action="store_true", help="List all registered series")
    parser.add_argument("--duration", type=int, default=40, help="Target duration in seconds")
    args = parser.parse_args()

    if args.list:
        series_list = list_all_series()
        print(json.dumps(series_list, indent=2))
        return

    if args.status:
        st = load_series(args.series)
        if not st:
            print(f"Series '{args.series}' not found.")
            return
        era = get_current_era(st)
        print(f"\n=======================================================")
        print(f" SERIES: {st.get('title')} ({st.get('series_id')})")
        print(f" Current Episode: #{st.get('current_episode')} | Timeline: Day {st.get('timeline_day')}")
        print(f" Current Era: {era.get('name')} - {era.get('subtitle')}")
        print(f" Protagonist: {st.get('character', {}).get('name')}")
        print(f" Condition: {st.get('character', {}).get('physical_condition')}")
        print(f" Gear: {st.get('character', {}).get('signature_gear')}")
        print(f" Last Cliffhanger: {st.get('last_cliffhanger')}")
        print(f" Total Episodes Produced: {len(st.get('episode_history', []))}")
        print(f"=======================================================\n")
        return

    if args.init:
        st = init_series(args.series, preset=args.preset)
        print(f"Series '{args.series}' initialized successfully. Current episode: #{st['current_episode']}")
        return

    if args.batch > 0:
        results = produce_batch(series_id=args.series, preset=args.preset, count=args.batch, target_duration=args.duration)
        print(json.dumps(results, indent=2))
        return

    # Default action: produce next episode
    res = produce_episode(series_id=args.series, preset=args.preset, target_duration=args.duration)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
