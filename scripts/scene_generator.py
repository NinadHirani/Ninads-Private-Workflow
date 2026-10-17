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
try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text


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

MOVIE_KEYWORDS = [
    "movie", "movies", "film", "films", "cinema", "hollywood", "batman", "oppenheimer",
    "interstellar", "joker", "marvel", "avengers", "spider-man", "spiderman", "iron man",
    "john wick", "godfather", "gladiator", "matrix", "star wars", "fight club", "inception",
    "lord of the rings", "peaky blinders", "breaking bad", "walter white", "cillian murphy",
    "tom cruise", "blade runner", "pulp fiction", "goodfellas", "scarface", "shawshank", "dark knight"
]

SCENE_INDICATORS = [
    "scene", "scenes", "clip", "clips", "fight", "fight scene", "battle", "moment",
    "dialogue", "quote", "speech", "action", "ending", "transformation", "climax",
    "monologue", "soundtrack", "original voice"
]

GAMING_KEYWORDS = [
    "game", "gaming", "minecraft", "gta", "elden ring", "cyberpunk", "zelda", "pokemon",
    "roblox", "fortnite", "valorant", "league of legends", "call of duty", "dark souls"
]

STOIC_KEYWORDS = [
    "stoic", "stoicism", "marcus aurelius", "seneca", "epictetus", "discipline",
    "mindset", "self-control", "inner peace", "philosophy", "wisdom", "warrior"
]

TECH_AI_KEYWORDS = [
    "ai", "artificial intelligence", "robot", "robotics", "tech", "quantum",
    "neural network", "singularity", "future technology", "cyberpunk", "agi"
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
    "relax", "relaxing", "calm", "sunset", "sunrise", "waterfall", "wildlife", "flowers",
    "stream", "landscape", "timelapse", "leaves", "deep forest", "birds", "bird"
]


def classify_topic(topic: str) -> dict:
    """Classifies topic into genre, style, audio mode, and visual mode."""
    t = (topic or "").lower().strip()
    is_scene = any(k in t for k in SCENE_INDICATORS)

    # 1. Nature & Pure Relaxation ASMR
    if any(k in t for k in NATURE_KEYWORDS):
        return {
            "category": "nature",
            "style": "chill",
            "visual_mode": "stock_video",
            "audio_mode": "nature_asmr",
            "music_mood": "calm_ambient",
            "voice_energy": "none",
            "badge_title": "🎧 PUT ON HEADPHONES • 4K ASMR",
        }

    # 2. Anime & Manga (Scene with Original Voice vs Commentary)
    if any(k in t for k in ANIME_KEYWORDS):
        if is_scene:
            return {
                "category": "anime_scene",
                "style": "anime",
                "visual_mode": "stock_video",
                "audio_mode": "original_voice",
                "music_mood": "epic_anime",
                "voice_energy": "original_character",
                "badge_title": f"🔥 {topic.upper()[:36]}",
            }
        else:
            return {
                "category": "anime",
                "style": "anime",
                "visual_mode": "ai_image",
                "audio_mode": "commentary_speech",
                "music_mood": "epic_anime",
                "voice_energy": "high",
                "badge_title": topic.upper()[:40],
            }

    # 3. Movie & Film (Scene with Original Voice vs Commentary)
    if any(k in t for k in MOVIE_KEYWORDS):
        if is_scene or any(w in t for w in ["scene", "clip", "dialogue", "movie", "film"]):
            return {
                "category": "movie_scene",
                "style": "cinematic",
                "visual_mode": "stock_video",
                "audio_mode": "original_voice",
                "music_mood": "cinematic_epic",
                "voice_energy": "original_character",
                "badge_title": f"🎬 {topic.upper()[:36]}",
            }
        else:
            return {
                "category": "movie",
                "style": "cinematic",
                "visual_mode": "ai_image",
                "audio_mode": "commentary_speech",
                "music_mood": "cinematic_epic",
                "voice_energy": "dramatic",
                "badge_title": topic.upper()[:40],
            }

    # 4. Standalone Scene Indicator (e.g. "epic fight scene", "interrogation scene")
    if is_scene:
        return {
            "category": "movie_scene",
            "style": "cinematic",
            "visual_mode": "stock_video",
            "audio_mode": "original_voice",
            "music_mood": "cinematic_epic",
            "voice_energy": "original_character",
            "badge_title": f"🎬 {topic.upper()[:36]}",
        }

    # 5. Stoic Philosophy & Mindset
    if any(k in t for k in STOIC_KEYWORDS):
        return {
            "category": "stoic",
            "style": "cinematic",
            "visual_mode": "ai_image",
            "audio_mode": "commentary_speech",
            "music_mood": "cinematic_epic",
            "voice_energy": "deep_reflective",
            "badge_title": "STOIC WISDOM",
        }

    # 6. Future Tech & AI Horizons
    if any(k in t for k in TECH_AI_KEYWORDS):
        return {
            "category": "tech_ai",
            "style": "viral",
            "visual_mode": "ai_image",
            "audio_mode": "commentary_speech",
            "music_mood": "phonk_hype",
            "voice_energy": "dynamic",
            "badge_title": "FUTURE OF TECH",
        }

    # 7. Mind-Blowing Facts & Mysteries
    if any(k in t for k in FACTS_MYSTERY_KEYWORDS):
        return {
            "category": "facts_mystery",
            "style": "viral",
            "visual_mode": "ai_image",
            "audio_mode": "commentary_speech",
            "music_mood": "suspense_phonk",
            "voice_energy": "dynamic",
            "badge_title": "MIND-BLOWING FACTS",
        }

    # 8. Gaming
    if any(k in t for k in GAMING_KEYWORDS):
        return {
            "category": "gaming",
            "style": "viral",
            "visual_mode": "ai_image",
            "audio_mode": "commentary_speech",
            "music_mood": "phonk_hype",
            "voice_energy": "high",
            "badge_title": topic.upper()[:40],
        }

    # 9. Sci-Fi & Cosmic Lore
    if any(k in t for k in SCIFI_LORE_KEYWORDS):
        return {
            "category": "scifi_lore",
            "style": "cinematic",
            "visual_mode": "ai_image",
            "audio_mode": "commentary_speech",
            "music_mood": "cosmic_ambient",
            "voice_energy": "dramatic",
            "badge_title": topic.upper()[:40],
        }

    # Default general fallback
    return {
        "category": "general",
        "style": "cinematic",
        "visual_mode": "ai_image",
        "audio_mode": "commentary_speech",
        "music_mood": "cinematic_epic",
        "voice_energy": "dynamic",
        "badge_title": topic.upper()[:40],
    }


def generate_scene_prompts(topic: str, category: str, n_scenes: int = 4) -> list:
    clean_topic = topic.strip()
    if category in ("anime", "anime_scene"):
        prompts = [
            f"{clean_topic}, iconic character portrait, intense eyes, dynamic aura, high detail anime masterpiece, vertical 9:16 orientation, vibrant lighting, dramatic atmosphere",
            f"{clean_topic}, epic battle power clash, shockwaves and glowing particles, cinematic anime action shot, vertical 9:16, sakuga style, hyper-detailed",
            f"{clean_topic}, legendary transformation or ultimate attack stance, destroyed cityscape ruins background, vertical 9:16 anime wallpaper, 8k art",
            f"{clean_topic}, cinematic victory scene at dusk, dramatic shadows, mysterious silhouette, vertical 9:16, award-winning anime visual",
        ]
    elif category in ("movie", "movie_scene"):
        prompts = [
            f"{clean_topic}, iconic cinematic movie scene, dramatic lighting, 35mm film grain, vertical 9:16, IMAX cinema still",
            f"{clean_topic}, intense character close-up dialogue moment, shallow depth of field, blockbuster movie aesthetic, vertical 9:16",
            f"{clean_topic}, legendary cinematic confrontation or action sequence, anamorphic lens flare, vertical 9:16, cinematic masterpiece",
            f"{clean_topic}, breathtaking wide cinematic climax shot, dramatic color grading, vertical 9:16 wallpaper",
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
    """Downloads a free 1080x1920 AI image from Pollinations with multi-model fallback."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    seed = random.randint(100000, 9999999)
    encoded = urllib.parse.quote(prompt)

    # Try models in order: flux (photorealistic/cinematic), default, then turbo
    candidate_urls = [
        f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={seed}",
        f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={seed}",
        f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=turbo&nologo=true&seed={seed}",
    ]

    for candidate_url in candidate_urls:
        logger.info("Generating AI scene with Pollinations...")
        req = urllib.request.Request(candidate_url, headers={"User-Agent": "Mozilla/5.0 (AI-Shorts-Factory/2.0)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) > 10000:
                    with open(out_path, "wb") as f:
                        f.write(data)
                    logger.info("Generated AI scene saved to %s (%d bytes)", out_path, len(data))
                    return True
        except Exception as e:
            logger.warning("Pollinations image attempt failed (%s): %s", candidate_url.split("&model=")[-1] if "&model=" in candidate_url else "default", redact(str(e)))
            time.sleep(1.0)

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

    # 1. Stock Video Mode (Collects authentic high-definition video clips for realistic cinematic results)
    prefer_real_video = os.getenv("PREFER_REAL_VIDEO", "1").strip().lower() in ("1", "true", "yes")
    should_search_stock = (info["visual_mode"] == "stock_video" or (prefer_real_video and info["category"] != "anime")) and not mock_mode()

    if should_search_stock:
        from scripts.content_finder import find_videos, _pick_file
        try:
            from scripts.logger import get_used_asset_ids
            used_ids = get_used_asset_ids()
        except Exception:
            used_ids = set()

        downloaded_clips = []
        queries = [topic]
        clean_topic = re.sub(r"[^\w\s]", " ", topic).strip()
        if clean_topic.lower() != topic.lower() and len(clean_topic) > 3:
            queries.append(clean_topic)

        # Contextual cinematic fallback keywords if exact topic is too narrow
        category_fallbacks = {
            "stoic": ["roman statue", "stoic philosophy", "ancient statue", "philosopher statue"],
            "tech_ai": ["humanoid robot", "artificial intelligence", "future technology", "cyberpunk city"],
            "facts_mystery": ["dark mystery", "cinematic shadows", "space cosmos", "surreal mystery"],
            "nature": ["nature landscape 4k", "forest sunlight", "ocean waves", "waterfall landscape"],
            "movie_scene": ["cinematic movie", "dramatic lighting", "movie scene"],
            "movie": ["cinematic movie", "dramatic lighting", "movie scene"],
            "scifi_lore": ["space cosmos", "black hole", "galaxy stars", "sci-fi futuristic"],
            "general": ["cinematic dramatic", "cinematic atmosphere", "cinematic portrait"],
        }
        if info["category"] in category_fallbacks:
            queries.extend(category_fallbacks[info["category"]])

        for q in queries:
            if len(downloaded_clips) >= n_scenes:
                break
            page = 1
            while len(downloaded_clips) < n_scenes and page <= 2:
                candidates = find_videos(q, page=page)
                if not candidates:
                    break
                for cand in candidates:
                    cand_id = str(cand.get("id", ""))
                    if cand_id in used_ids or f"pexels_{cand_id}" in used_ids or f"pixabay_{cand_id}" in used_ids:
                        continue
                    best_file, _ = _pick_file(cand.get("video_files", []))
                    if not best_file or not best_file.get("link"):
                        continue
                    if best_file.get("link") in used_ids:
                        continue
                    dl = download_video(best_file["link"])
                    if dl.get("status") == "SUCCESS":
                        downloaded_clips.append({"file_path": dl["file_path"], "asset_id": cand_id, "url": best_file.get("link")})
                        if len(downloaded_clips) >= n_scenes:
                            break
                page += 1

        if downloaded_clips:
            for idx, item in enumerate(downloaded_clips):
                dur = frames_per_scene + (remainder_frames if idx == len(downloaded_clips) - 1 else 0)
                scenes.append({
                    "type": "video",
                    "src": item["file_path"],
                    "asset_id": item["asset_id"],
                    "asset_url": item["url"],
                    "durationInFrames": dur,
                })
            if callable(on_progress):
                on_progress("scenes", "done", f"Collected {len(scenes)} fresh realistic video clips")
            return scenes

    # 2. AI Visual Generation Mode (Anime, Sci-Fi, Gaming, Facts, etc.)
    prompts = generate_scene_prompts(topic, info["category"], n_scenes)

    for idx, p in enumerate(prompts):
        if idx > 0:
            time.sleep(1.2)
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
