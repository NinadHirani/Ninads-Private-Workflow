#!/usr/bin/env python3
"""
Scene Generator - AI Shorts Factory
Intelligently classifies any topic (Anime, Gaming, Sci-Fi Lore, Mystery Facts, Nature),
selects the optimal visual mode (AI Scene Generation vs Stock Footage),
and generates 1080x1920 high-definition scenes.
"""

import os
import re
import sys
import time
import json
import base64
import random
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger("scene_generator")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.content_finder import find_videos, mock_mode
from scripts.downloader import download_video


ANIME_KEYWORDS = [
    "anime", "manga", "saitama", "one punch", "one-punch", "goku", "naruto", "luffy",
    "jujutsu", "gojo", "sukuna", "attack on titan", "eren", "demon slayer", "tanjiro",
    "bleach", "ichigo", "death note", "solo leveling", "jinwoo", "hunter x hunter",
    "dragon ball", "zoro", "otaku", "waifu", "shonen", "chainsaw man"
]

GAMING_KEYWORDS = [
    "game", "gaming", "minecraft", "gta", "elden ring", "cyberpunk", "zelda", "pokemon",
    "roblox", "fortnite", "valorant", "league of legends", "call of duty", "dark souls"
]

SCIFI_LORE_KEYWORDS = [
    "space", "universe", "alien", "galaxy", "black hole", "cosmic", "scifi", "sci-fi",
    "future", "mythology", "gods", "zeus", "lovecraft", "ancient", "pyramids"
]

FACTS_MYSTERY_KEYWORDS = [
    "fact", "facts", "mystery", "paradox", "psychology", "secret", "creepy",
    "dark truth", "unsolved", "did you know", "mind-blowing", "science", "bizarre"
]

NATURE_KEYWORDS = [
    "nature", "forest", "ocean", "waves", "rain", "mountain", "river", "aurora",
    "relax", "relaxing", "calm", "sunset", "sunrise", "waterfall", "wildlife", "flowers"
]


def classify_topic(topic: str) -> dict:
    """Classifies topic into genre, style, and visual mode."""
    t = (topic or "").lower().strip()

    # 1. Anime
    if any(k in t for k in ANIME_KEYWORDS):
        return {
            "category": "anime",
            "style": "anime",
            "visual_mode": "ai_image",
            "music_mood": "epic_anime",
            "voice_energy": "high",
            "badge_title": topic.upper()[:40],
        }

    # 2. Gaming
    if any(k in t for k in GAMING_KEYWORDS):
        return {
            "category": "gaming",
            "style": "viral",
            "visual_mode": "ai_image",
            "music_mood": "phonk_hype",
            "voice_energy": "high",
            "badge_title": topic.upper()[:40],
        }

    # 3. Sci-Fi & Lore
    if any(k in t for k in SCIFI_LORE_KEYWORDS):
        return {
            "category": "scifi_lore",
            "style": "cinematic",
            "visual_mode": "ai_image",
            "music_mood": "cosmic_ambient",
            "voice_energy": "dramatic",
            "badge_title": topic.upper()[:40],
        }

    # 4. Mind-Blowing Facts & Mysteries
    if any(k in t for k in FACTS_MYSTERY_KEYWORDS):
        return {
            "category": "facts_mystery",
            "style": "viral",
            "visual_mode": "ai_image",
            "music_mood": "suspense_phonk",
            "voice_energy": "dynamic",
            "badge_title": topic.upper()[:40],
        }

    # 5. Nature & Relaxation
    if any(k in t for k in NATURE_KEYWORDS):
        return {
            "category": "nature",
            "style": "chill",
            "visual_mode": "stock_video",
            "music_mood": "calm_ambient",
            "voice_energy": "soothing",
            "badge_title": topic.upper()[:40],
        }

    # Default general fallback
    return {
        "category": "general",
        "style": "cinematic",
        "visual_mode": "ai_image",
        "music_mood": "cinematic_epic",
        "voice_energy": "dynamic",
        "badge_title": topic.upper()[:40],
    }


def generate_scene_prompts(topic: str, category: str, n_scenes: int = 4) -> list:
    clean_topic = topic.strip()
    if category == "anime":
        prompts = [
            f"{clean_topic}, iconic character portrait, intense eyes, dynamic aura, high detail anime masterpiece, vertical 9:16 orientation, vibrant lighting, dramatic atmosphere",
            f"{clean_topic}, epic battle power clash, shockwaves and glowing particles, cinematic anime action shot, vertical 9:16, sakuga style, hyper-detailed",
            f"{clean_topic}, legendary transformation or ultimate attack stance, destroyed cityscape ruins background, vertical 9:16 anime wallpaper, 8k art",
            f"{clean_topic}, cinematic victory scene at dusk, dramatic shadows, mysterious silhouette, vertical 9:16, award-winning anime visual",
        ]
    elif category == "gaming":
        prompts = [
            f"{clean_topic}, high-octane gaming character hero art, neon cyber glow, cinematic dynamic angle, vertical 9:16, unreal engine 5 render",
            f"{clean_topic}, intense boss fight arena, explosive energy and sparks, vertical 9:16, photorealistic gaming action scene",
            f"{clean_topic}, secret hidden game world location, breathtaking atmospheric lighting, vertical 9:16, concept art",
            f"{clean_topic}, legendary weapon or triumph moment, glorious golden backlight, vertical 9:16 wallpaper",
        ]
    elif category == "scifi_lore":
        prompts = [
            f"{clean_topic}, colossal celestial phenomenon, deep space cosmic nebula, breathtaking scale, vertical 9:16, James Webb telescope aesthetic",
            f"{clean_topic}, ancient futuristic alien mega-structure, glowing glyphs, mystery and awe, vertical 9:16, cinematic sci-fi art",
            f"{clean_topic}, event horizon of a black hole bending light and stars, cosmic distortion, vertical 9:16, 8k render",
            f"{clean_topic}, futuristic explorer witnessing an otherworldly monolith, atmospheric dust, vertical 9:16 wallpaper",
        ]
    elif category == "facts_mystery":
        prompts = [
            f"{clean_topic}, mysterious dark visual concept, glowing question and enigma, hyper-detailed surrealism, vertical 9:16, cinematic noir",
            f"{clean_topic}, dramatic scientific discovery, microscopic or astronomical scale, brilliant luminescence, vertical 9:16",
            f"{clean_topic}, forbidden secret chamber or ancient artifact glowing in the dark, cinematic mystery, vertical 9:16",
            f"{clean_topic}, mind-bending optical reality twist, surreal masterpiece, vertical 9:16, ultra-sharp",
        ]
    else:
        prompts = [
            f"{clean_topic}, dramatic cinematic opening scene, golden hour rays, vertical 9:16, photorealistic masterpiece",
            f"{clean_topic}, intense close-up detail, sharp focus, atmospheric depth of field, vertical 9:16",
            f"{clean_topic}, sweeping wide perspective, breathtaking mood, vertical 9:16 cinematic still",
            f"{clean_topic}, triumphant closing moment, high contrast, vertical 9:16 award-winning photography",
        ]

    while len(prompts) < n_scenes:
        prompts.append(prompts[len(prompts) % len(prompts)])
    return prompts[:n_scenes]


def download_pollinations_image(prompt: str, out_path: str) -> bool:
    """Downloads a free 1080x1920 AI image from Pollinations (default free model)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    seed = random.randint(100000, 9999999)
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={seed}"

    logger.info("Generating AI scene with Pollinations...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (AI-Shorts-Factory/2.0)"})
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = resp.read()
            if len(data) > 10000:
                with open(out_path, "wb") as f:
                    f.write(data)
                logger.info("Generated AI scene saved to %s (%d bytes)", out_path, len(data))
                return True
    except Exception as e:
        logger.warning("Pollinations image generation failed: %s", e)

    return False


def collect_scenes(topic: str, total_duration_sec: float, out_dir: str,
                   n_scenes: int = 4, on_progress = None) -> list:
    """Collects or generates scenes for Remotion composition."""
    info = classify_topic(topic)
    os.makedirs(out_dir, exist_ok=True)
    scenes = []

    fps = 30
    total_frames = int(total_duration_sec * fps)
    frames_per_scene = total_frames // n_scenes
    remainder_frames = total_frames - (frames_per_scene * n_scenes)

    if callable(on_progress):
        on_progress("scenes", "running", f"Mode: {info['visual_mode']}, Category: {info['category']}")

    # 1. Stock Video Mode (for Nature / Real-World)
    if info["visual_mode"] == "stock_video" and not mock_mode():
        candidates = find_videos(topic)
        if candidates:
            downloaded_clips = []
            from content_finder import _pick_file
            for cand in candidates[:n_scenes]:
                best_file, _ = _pick_file(cand.get("video_files", []))
                if best_file and best_file.get("link"):
                    dl = download_video(best_file["link"])
                    if dl.get("status") == "SUCCESS":
                        downloaded_clips.append(dl["file_path"])

            if downloaded_clips:
                for idx, clip in enumerate(downloaded_clips):
                    dur = frames_per_scene + (remainder_frames if idx == len(downloaded_clips) - 1 else 0)
                    scenes.append({
                        "type": "video",
                        "src": clip,
                        "durationInFrames": dur,
                    })
                if callable(on_progress):
                    on_progress("scenes", "done", f"Collected {len(scenes)} stock video clips")
                return scenes

    # 2. AI Visual Generation Mode (Anime, Sci-Fi, Gaming, Facts, etc.)
    prompts = generate_scene_prompts(topic, info["category"], n_scenes)

    for idx, p in enumerate(prompts):
        if callable(on_progress):
            on_progress("scenes", "running", f"Generating scene {idx+1}/{len(prompts)}")
        img_file = os.path.join(out_dir, f"scene_{idx}.jpg")
        success = download_pollinations_image(p, img_file)

        if not success or not os.path.exists(img_file):
            logger.warning("Could not download scene %d, using local fallback sample", idx)
            mock_sample = os.path.join(ROOT, "tests", "sample.mp4")
            if os.path.exists(mock_sample):
                dur = frames_per_scene + (remainder_frames if idx == len(prompts) - 1 else 0)
                scenes.append({
                    "type": "video",
                    "src": mock_sample,
                    "durationInFrames": dur,
                })
                continue

        dur = frames_per_scene + (remainder_frames if idx == len(prompts) - 1 else 0)
        scenes.append({
            "type": "image",
            "src": img_file,
            "durationInFrames": dur,
        })

    if callable(on_progress):
        on_progress("scenes", "done", f"Generated {len(scenes)} AI visual scenes")

    return scenes
