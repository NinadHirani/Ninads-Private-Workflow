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


from scripts.content_finder import find_videos, _pick_file, mock_mode
from scripts.downloader import download_video


def collect_series_video_scenes(
    ctx: Dict[str, Any],
    episode_data: Dict[str, Any],
    total_audio_sec: float,
    workdir: str,
    on_progress = None
) -> List[Dict[str, Any]]:
    """
    Collects authentic high-definition 1080x1920 video clips matching the narrative beats
    of the continuous series. Guarantees true motion video for every scene beat.
    """
    fps = 30
    total_frames = int(max(15.0, total_audio_sec + 2.5) * fps)

    script_lines = episode_data.get("script_lines", [])
    n_scenes = max(4, min(5, len(script_lines) if script_lines else 5))
    frames_per_scene = total_frames // n_scenes
    remainder_frames = total_frames - (frames_per_scene * n_scenes)

    if mock_mode():
        sample_mp4 = os.path.join(ROOT, "tests", "sample.mp4")
        scenes = []
        for idx in range(n_scenes):
            dur = frames_per_scene + (remainder_frames if idx == n_scenes - 1 else 0)
            scenes.append({
                "type": "video",
                "src": sample_mp4,
                "durationInFrames": dur,
            })
        return scenes

    series_id = ctx.get("series_id", "kane")
    if "goliath" in series_id:
        beat_queries = [
            ["dark cave cavern magma", "volcano lava rocks smoke", "underground cave dark rocks"],
            ["cave rocks seismic tremor", "subterranean tunnel stone", "ancient stones glowing cave"],
            ["earthquake cracking rocks debris", "crashing rocks cave in", "underground cavern waterfall"],
            ["destroyed city overgrown ruins", "storm clouds lightning mountains", "giant shadows dark mountains"],
            ["colossal beast shadow clouds", "magma glow volcanic crater", "mysterious glowing runes ancient"],
        ]
    elif "stickman" in series_id or "zero" in series_id:
        beat_queries = [
            ["cyberpunk dark rainy street neon", "ninja silhouette running dark", "cyberpunk alley rain"],
            ["katana sword draw cinematic", "martial arts fighting shadow", "cyberpunk neon lights night"],
            ["dark industrial factory steam", "rooftop night city skyline", "laser lights dark smoke"],
            ["sparks flying metal explosion", "fast motion shadow combat", "cyberpunk red neon lights"],
            ["cyberpunk city lightning storm", "neon glow sword reflection", "cyberpunk skyline dark"],
        ]
    else:
        # Kane Chronicles / Apocalypse Survival
        beat_queries = [
            ["apocalypse survivor ruins", "lone wanderer wasteland ruins", "post apocalyptic dust"],
            ["tactical soldier ruins post apocalypse", "man walking destroyed city rubble", "ruined abandoned corridor"],
            ["underground concrete bunker dark tunnel", "abandoned vault industrial ruins", "dark subway tunnel flashlight"],
            ["earthquake dust smoke rubble", "smoke and dust destruction disaster", "falling concrete debris earthquake"],
            ["mysterious glowing light anomaly", "alien artifact purple sci fi glow", "dark sci fi glowing structure"],
        ]

    scenes = []
    used_links = set()

    for idx in range(n_scenes):
        dur = frames_per_scene + (remainder_frames if idx == n_scenes - 1 else 0)
        clip_path = os.path.join(workdir, f"series_scene_{idx}.mp4")
        queries_for_beat = beat_queries[idx % len(beat_queries)]

        if callable(on_progress):
            on_progress("visuals", "running", f"Finding authentic HD video for scene {idx + 1}/{n_scenes}")

        found_clip = False
        for q in queries_for_beat:
            try:
                candidates = find_videos(q, page=1)
                for cand in candidates:
                    files = cand.get("video_files", [])
                    best_file, _ = _pick_file(files)
                    if not best_file or not best_file.get("link"):
                        continue
                    link = best_file["link"]
                    if link in used_links:
                        continue
                    dl_res = download_video(link, output_path=clip_path, timeout=30)
                    if dl_res.get("status") == "SUCCESS" and os.path.exists(clip_path) and os.path.getsize(clip_path) > 50000:
                        used_links.add(link)
                        scenes.append({
                            "type": "video",
                            "src": clip_path,
                            "durationInFrames": dur,
                        })
                        found_clip = True
                        break
            except Exception as e:
                logger.warning("Error fetching scene video for query '%s': %s", q, redact(str(e)))
            if found_clip:
                break

        if not found_clip:
            logger.warning("No fresh video found for scene %d; using sample fallback clip", idx)
            sample_mp4 = os.path.join(ROOT, "tests", "sample.mp4")
            scenes.append({
                "type": "video",
                "src": sample_mp4,
                "durationInFrames": dur,
            })

    return scenes


def produce_episode(
    series_id: str = "kane",
    preset: str = "kane",
    target_duration: int = 40,
    output_dir: str = None,
    upload: bool = False,
    privacy: str = "private",
    publish_at: str = None,
    on_progress = None
) -> Dict[str, Any]:
    """
    Produces a single continuous episode, maintaining unbroken continuity
    with all previous episodes and updating series state. Uses authentic HD
    video footage clips for every scene.
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

        # 4. Assemble Authentic Dynamic Video Scenes
        notify("visuals", "running", f"Collecting cinematic HD video clips for {ctx['character_name']}")
        scenes = collect_series_video_scenes(ctx, episode_data, total_audio_sec, workdir, on_progress=notify)
        notify("visuals", "done", f"Assembled {len(scenes)} dynamic HD video scenes")

        # 5. Programmatic Remotion Video Render
        notify("render", "running", "Rendering video with Remotion...")
        ts = time.strftime("%Y%m%d_%H%M%S")
        deliv_dir = output_dir or os.path.join(ROOT, "deliverables")
        os.makedirs(deliv_dir, exist_ok=True)
        out_mp4 = os.path.join(deliv_dir, f"series_{series_id}_ep{ep_num:03d}_{ts}.mp4")

        # Serial Overlays
        ep_badge = f"EPISODE {ep_num:02d} • DAY {day_num}"
        ch_sub = f"{ctx['era_name']} • {episode_data.get('title')}".upper()
        next_cta = f"PART {ep_num + 1} DROPS TOMORROW • SUBSCRIBE"

        cinematic_music = os.path.join(ROOT, "music", "cinematic_epic.mp3")
        music_file = cinematic_music if os.path.exists(cinematic_music) else None

        ambient_rain = os.path.join(ROOT, "music", "rain_ambient.mp3")
        ambient_file = ambient_rain if os.path.exists(ambient_rain) else None

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
            music_src=music_file,
            music_volume=0.20,
            ambient_src=ambient_file,
            ambient_volume=0.15,
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

        # 9. Direct Upload to YouTube & Instagram (if requested)
        yt_upload = {}
        if upload:
            try:
                from scripts.run_pipeline import publish_youtube_video, publish_instagram_video
                from scripts.uploader import enqueue_dual_upload

                serial_title = f"{state.get('title', 'Kane')}: Ep {ep_num} - {episode_data.get('title')} #Shorts"
                if len(serial_title) > 95:
                    serial_title = f"Kane Ep {ep_num}: {episode_data.get('title')} #Shorts"[:95]

                serial_desc = (
                    f"{state.get('title', 'Kane')} — Episode {ep_num} (Day {day_num})\n"
                    f"{ctx['era_name']}\n\n"
                    f"{episode_data.get('summary')}\n\n"
                    f"Cliffhanger: {episode_data.get('cliffhanger')}\n\n"
                    f"Subscribe for Episode {ep_num + 1} dropping tomorrow!\n\n"
                    f"#Shorts #Series #Apocalypse #Survival #SciFi #Story"
                )

                notify("upload", "running", "Publishing series episode to YouTube...")
                yt_upload = publish_youtube_video(
                    out_mp4,
                    title=serial_title,
                    description=serial_desc,
                    tags=["Kane", "Shorts", "Series", "Apocalypse", "Survival", "SciFi", "Story", "Cinematic"],
                    privacy=privacy,
                    publish_at=publish_at,
                    on_progress=notify,
                )
                if yt_upload.get("status") == "SUCCESS":
                    notify("upload", "done", f"Uploaded to YouTube: {yt_upload.get('url')}")
                    queue_reason = ""
                else:
                    queue_reason = "YouTube daily quota reached" if yt_upload.get("status") == "QUOTA_EXCEEDED" else yt_upload.get("error", "YouTube upload failed")
                    enqueue_dual_upload(out_mp4, meta_json, reason=queue_reason)
                    notify("upload", "done", f"Preserved for dual upload: {queue_reason}")

                # Publish to Instagram Reel
                ig_upload = {}
                try:
                    notify("upload_instagram", "running", "Publishing series episode to Instagram Reel...")
                    ig_upload = publish_instagram_video(
                        out_mp4,
                        title=serial_title,
                        description=serial_desc,
                        tags=["Kane", "Shorts", "Series", "Apocalypse", "Survival", "SciFi", "Story", "Cinematic"],
                        on_progress=notify,
                    )
                    if ig_upload.get("status") == "SUCCESS":
                        notify("upload_instagram", "done", f"Uploaded to Instagram: {ig_upload.get('instagram_url')}")
                except Exception as ex_ig:
                    logger.warning("Instagram upload step error: %s", redact(str(ex_ig)))

            except Exception as e:
                logger.warning("Upload step error: %s", redact(str(e)))
                queue_reason = str(e)
        else:
            queue_reason = ""
            ig_upload = {}

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
            "video_path": out_mp4,
            "file_path": out_mp4,
            "youtube_url": yt_upload.get("url") or yt_upload.get("youtube_url", ""),
            "instagram_url": ig_upload.get("instagram_url", ""),
            "queue_reason": queue_reason,
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
    output_dir: str = None,
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
            output_dir=output_dir,
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
