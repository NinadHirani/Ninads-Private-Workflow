#!/usr/bin/env python3
"""
Remotion Renderer - AI Shorts Factory
Bridges Python pipeline with Remotion CLI to render programmatic 1080x1920
vertical videos with dynamic kinetic captions and Ken Burns camera animations.
Uses self-contained base64 data URIs for images and audio to guarantee 100%
reliability with zero bundle 404s or network dependency.
"""

import os
import sys
import json
import time
import shutil
import base64
import logging
import subprocess

logger = logging.getLogger("remotion_renderer")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION_DIR = os.path.join(ROOT, "remotion")


def file_to_data_uri(path: str, mime: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def normalize_words(words: list, total_duration_sec: float = 30.0, fallback_text: str = "") -> list:
    normalized = []
    if words:
        for item in words:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                normalized.append({
                    "word": str(item[0]).strip(),
                    "start": float(item[1]),
                    "end": float(item[2]),
                })
            elif isinstance(item, dict) and "word" in item:
                normalized.append({
                    "word": str(item["word"]).strip(),
                    "start": float(item.get("start", 0)),
                    "end": float(item.get("end", 0)),
                })

    if not normalized and fallback_text:
        # Generate synthetic smooth timings spread across the spoken duration
        raw_words = [w.strip() for w in fallback_text.split() if w.strip()]
        if raw_words:
            dur_per_word = max(0.2, (total_duration_sec - 1.0) / len(raw_words))
            for i, w in enumerate(raw_words):
                st = round(i * dur_per_word, 2)
                en = round((i + 1) * dur_per_word, 2)
                normalized.append({"word": w, "start": st, "end": en})

    return normalized


def render_with_remotion(
    scenes: list,
    voiceover_wav: str = None,
    words: list = None,
    output_mp4: str = "",
    title: str = "",
    style: str = "anime",
    music_src: str = None,
    music_volume: float = 0.18,
    ambient_src: str = None,
    ambient_volume: float = 0.65,
    logo_src: str = None,
    fallback_text: str = "",
    use_original_audio: bool = False,
    on_progress=None,
) -> dict:
    started = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)

    if os.getenv("SHORTS_MOCK") == "1":
        total_frames = max(30, sum(s.get("durationInFrames", 30) for s in scenes))
        dur = total_frames / 30.0
        sample = os.getenv("SHORTS_SAMPLE_VIDEO") or os.path.join(ROOT, "tests", "sample.mp4")
        if os.path.exists(sample):
            subprocess.run([
                "ffmpeg", "-y", "-i", sample, "-t", str(int(dur)),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264", "-c:a", "aac", output_mp4
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={dur}",
                            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dur}", "-c:v", "libx264", "-c:a", "aac", output_mp4],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "status": "SUCCESS",
            "file_path": output_mp4,
            "duration_frames": total_frames,
            "duration_sec": round(dur, 2),
            "render_time_sec": 0.1,
        }

    run_id = f"run_{int(time.time() * 1000)}"
    public_assets_dir = os.path.join(REMOTION_DIR, "public", "assets", run_id)
    os.makedirs(public_assets_dir, exist_ok=True)
    props_file = None

    try:
        # 1. Voiceover data URI (if provided and not in original audio mode)
        vo_uri = ""
        if not use_original_audio and voiceover_wav and os.path.exists(voiceover_wav):
            vo_uri = file_to_data_uri(voiceover_wav, "audio/wav")

        # 2. Process Scenes
        processed_scenes = []
        for idx, sc in enumerate(scenes):
            raw_src = sc.get("src", "")
            src_path = raw_src if os.path.isabs(raw_src) else os.path.join(ROOT, raw_src)
            sc_vol = sc.get("volume")
            if sc_vol is None:
                sc_vol = 1.0 if use_original_audio else 0.0

            if sc["type"] == "image" and os.path.exists(src_path):
                img_uri = file_to_data_uri(src_path, "image/jpeg")
                processed_scenes.append({
                    "type": "image",
                    "src": img_uri,
                    "durationInFrames": sc["durationInFrames"],
                    "volume": sc_vol,
                })
            elif sc["type"] == "video" and os.path.exists(src_path):
                # Stage video inside remotion/public/assets for reliable Chromium playback
                ext = os.path.splitext(src_path)[1] or ".mp4"
                staged_name = f"clip_{idx}{ext}"
                staged_path = os.path.join(public_assets_dir, staged_name)
                try:
                    shutil.copy2(src_path, staged_path)
                    relative_src = f"assets/{run_id}/{staged_name}"
                except Exception as e:
                    logger.warning("Could not stage video clip %s: %s", src_path, e)
                    relative_src = src_path
                processed_scenes.append({
                    "type": "video",
                    "src": relative_src,
                    "durationInFrames": sc["durationInFrames"],
                    "volume": sc_vol,
                })
            else:
                processed_scenes.append({
                    "type": sc["type"],
                    "src": sc["src"],
                    "durationInFrames": sc["durationInFrames"],
                    "volume": sc_vol,
                })

        # 3. Background Music data URI if present
        music_uri = None
        if music_src and (not use_original_audio or music_volume > 0):
            abs_music = music_src if os.path.isabs(music_src) else os.path.join(ROOT, music_src)
            if os.path.exists(abs_music):
                ext = os.path.splitext(abs_music)[1].lstrip(".") or "mp3"
                music_uri = file_to_data_uri(abs_music, f"audio/{ext}")

        # 3b. Ambient Soundscape data URI if present (nature ASMR)
        ambient_uri = None
        if ambient_src:
            abs_ambient = ambient_src if os.path.isabs(ambient_src) else os.path.join(ROOT, ambient_src)
            if os.path.exists(abs_ambient):
                ext = os.path.splitext(abs_ambient)[1].lstrip(".") or "mp3"
                ambient_uri = file_to_data_uri(abs_ambient, f"audio/{ext}")

        # 4. Logo data URI if present
        logo_uri = None
        if logo_src and os.path.exists(logo_src):
            logo_uri = file_to_data_uri(logo_src, "image/png")

        total_frames = sum(s["durationInFrames"] for s in processed_scenes)
        total_sec = total_frames / 30.0

        clean_words = [] if use_original_audio else normalize_words(words or [], total_duration_sec=total_sec, fallback_text=fallback_text)

        props = {
            "scenes": processed_scenes,
            "voiceoverSrc": vo_uri,
            "words": clean_words,
            "musicSrc": music_uri,
            "musicVolume": music_volume,
            "ambientSrc": ambient_uri,
            "ambientVolume": ambient_volume,
            "style": style,
            "title": title,
            "logoSrc": logo_uri,
            "durationInFrames": max(30, total_frames),
            "useOriginalAudio": use_original_audio,
        }

        props_file = os.path.join(ROOT, "remotion", f"props_{int(time.time() * 1000)}.json")
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(props, f)

        if callable(on_progress):
            on_progress("render", "running", f"Rendering with Remotion ({total_frames} frames)...")

        # 5. Invoke npx remotion render
        cmd = [
            "npx",
            "remotion",
            "render",
            "src/index.ts",
            "ShortsVideo",
            os.path.abspath(output_mp4),
            f"--props={os.path.abspath(props_file)}",
            "--concurrency=2",
            "--gl=angle",
        ]

        proc = subprocess.run(
            cmd,
            cwd=REMOTION_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=int(os.getenv("FFMPEG_TIMEOUT_SEC", "600")),
        )

        if proc.returncode != 0:
            logger.error("Remotion render failed with exit code %d:\n%s", proc.returncode, proc.stdout)
            return {
                "status": "FAILED",
                "error": f"Remotion render exited with {proc.returncode}: {proc.stdout[-500:]}",
            }

        if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < 50000:
            return {
                "status": "FAILED",
                "error": "Rendered MP4 file is missing or suspiciously small",
            }

        elapsed = round(time.time() - started, 2)
        logger.info("Remotion render completed successfully in %.2fs -> %s", elapsed, output_mp4)

        if callable(on_progress):
            on_progress("render", "done", f"Rendered 1080x1920 MP4 in {elapsed}s")

        return {
            "status": "SUCCESS",
            "file_path": output_mp4,
            "duration_frames": total_frames,
            "duration_sec": round(total_sec, 2),
            "render_time_sec": elapsed,
        }

    except subprocess.TimeoutExpired:
        return {"status": "FAILED", "error": "Remotion render timed out"}
    except Exception as exc:
        logger.exception("Error during Remotion render")
        return {"status": "FAILED", "error": str(exc)}
    finally:
        try:
            if props_file and os.path.exists(props_file):
                os.remove(props_file)
        except Exception:
            pass
        try:
            if public_assets_dir and os.path.exists(public_assets_dir):
                shutil.rmtree(public_assets_dir, ignore_errors=True)
        except Exception:
            pass
