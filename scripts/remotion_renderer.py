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
    voiceover_wav: str,
    words: list,
    output_mp4: str,
    title: str = "",
    style: str = "anime",
    music_src: str = None,
    logo_src: str = None,
    fallback_text: str = "",
    on_progress=None,
) -> dict:
    started = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)

    try:
        # 1. Voiceover data URI
        vo_uri = ""
        if voiceover_wav and os.path.exists(voiceover_wav):
            vo_uri = file_to_data_uri(voiceover_wav, "audio/wav")

        # 2. Process Scenes
        processed_scenes = []
        for idx, sc in enumerate(scenes):
            src_path = sc["src"]
            if sc["type"] == "image" and os.path.exists(src_path):
                img_uri = file_to_data_uri(src_path, "image/jpeg")
                processed_scenes.append({
                    "type": "image",
                    "src": img_uri,
                    "durationInFrames": sc["durationInFrames"],
                })
            else:
                # Video files or fallback URLs
                processed_scenes.append({
                    "type": sc["type"],
                    "src": sc["src"],
                    "durationInFrames": sc["durationInFrames"],
                })

        # 3. Background Music data URI if present
        music_uri = None
        if music_src and os.path.exists(music_src):
            ext = os.path.splitext(music_src)[1].lstrip(".") or "mp3"
            music_uri = file_to_data_uri(music_src, f"audio/{ext}")

        # 4. Logo data URI if present
        logo_uri = None
        if logo_src and os.path.exists(logo_src):
            logo_uri = file_to_data_uri(logo_src, "image/png")

        total_frames = sum(s["durationInFrames"] for s in processed_scenes)
        total_sec = total_frames / 30.0

        clean_words = normalize_words(words, total_duration_sec=total_sec, fallback_text=fallback_text)

        props = {
            "scenes": processed_scenes,
            "voiceoverSrc": vo_uri,
            "words": clean_words,
            "musicSrc": music_uri,
            "musicVolume": 0.16,
            "style": style,
            "title": title,
            "logoSrc": logo_uri,
            "durationInFrames": max(30, total_frames),
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

        logger.info("Executing Remotion render: %s", " ".join(cmd))
        proc = subprocess.run(
            cmd,
            cwd=REMOTION_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=int(os.getenv("FFMPEG_TIMEOUT_SEC", "600")),
        )

        try:
            if os.path.exists(props_file):
                os.remove(props_file)
        except Exception:
            pass

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
