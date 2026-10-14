#!/usr/bin/env python3
"""
Sound & Music Manager - AI Shorts Factory
Provides context-aware background music and realistic natural ambient soundscapes
(rain, ocean waves, stream, forest wind) for nature videos, plus genre-matched
musical beats (phonk, suspense, epic, lofi) for viral story shorts.
"""

import os
import sys
import logging
import subprocess

logger = logging.getLogger("sound_manager")
try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC_DIR = os.path.join(ROOT, "music")


def ensure_music_dir():
    os.makedirs(MUSIC_DIR, exist_ok=True)


def _generate_synthetic_track(name: str, filter_str: str, duration: int = 35) -> str:
    ensure_music_dir()
    out_path = os.path.join(MUSIC_DIR, f"{name}.mp3")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        return out_path

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", filter_str,
        "-t", str(duration),
        "-ac", "2",
        "-ar", "44100",
        "-b:a", "128k",
        out_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if res.returncode == 0 and os.path.exists(out_path):
            logger.info("Generated soundscape track: %s", out_path)
            return out_path
    except Exception as e:
        logger.warning("Could not generate synthetic sound %s: %s", name, redact(str(e)))
    return out_path if os.path.exists(out_path) else None


def get_nature_soundscape(topic: str, duration: int = 30) -> str:
    """Returns a realistic natural ambient soundscape (rain, ocean, forest, river)."""
    t = (topic or "").lower()

    if any(k in t for k in ["rain", "storm", "thunder", "droplet"]):
        track = "nature_rain"
        filt = f"anoisesrc=d={duration}:c=pink:r=44100:a=0.12,lowpass=f=1200,highpass=f=200,volume=1.8"
    elif any(k in t for k in ["ocean", "wave", "beach", "sea", "surf"]):
        track = "nature_ocean"
        filt = f"anoisesrc=d={duration}:c=brown:r=44100:a=0.22,tremolo=f=0.12:d=0.85,lowpass=f=750,volume=2.2"
    elif any(k in t for k in ["river", "stream", "waterfall", "creek"]):
        track = "nature_river"
        filt = f"anoisesrc=d={duration}:c=pink:r=44100:a=0.16,bandpass=f=1400:w=1100,volume=1.7"
    else:
        # Forest / wind / calm nature
        track = "nature_forest"
        filt = f"anoisesrc=d={duration}:c=brown:r=44100:a=0.14,tremolo=f=0.08:d=0.7,lowpass=f=600,volume=1.6"

    path = _generate_synthetic_track(track, filt, duration=duration + 5)
    return path


def get_music_track(mood: str = "calm_ambient", duration: int = 30) -> str:
    """Returns a mood-matched background music track."""
    m = (mood or "calm_ambient").lower()

    if "phonk" in m or "hype" in m:
        track = "phonk_hype"
        # Driving low bass pulses with filtered rhythm
        filt = f"anoisesrc=d={duration}:c=brown:r=44100:a=0.25,tremolo=f=2.2:d=0.9,lowpass=f=450,volume=2.0"
    elif "suspense" in m or "mystery" in m:
        track = "suspense_mystery"
        # Deep eerie sub drone with subtle pitch swell
        filt = f"anoisesrc=d={duration}:c=brown:r=44100:a=0.2,tremolo=f=0.2:d=0.6,lowpass=f=300,volume=2.2"
    elif "epic" in m or "cinematic" in m:
        track = "cinematic_epic"
        # Resonant swelling atmospheric rumble & strings vibe
        filt = f"anoisesrc=d={duration}:c=pink:r=44100:a=0.15,tremolo=f=0.3:d=0.75,bandpass=f=600:w=500,volume=2.0"
    else:
        # Calm ambient soft pads
        track = "calm_ambient"
        filt = f"anoisesrc=d={duration}:c=pink:r=44100:a=0.08,tremolo=f=0.15:d=0.6,lowpass=f=500,volume=1.3"

    path = _generate_synthetic_track(track, filt, duration=duration + 5)
    return path


def check_video_audio_track(file_path: str) -> dict:
    """
    Inspects whether a video file has an audio track and whether it contains audible sound.
    Returns: {"has_audio": bool, "has_audible_sound": bool, "max_volume_db": float}
    """
    if not file_path or not os.path.exists(file_path):
        return {"has_audio": False, "has_audible_sound": False, "max_volume_db": -99.0}
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if not res.stdout.strip():
            return {"has_audio": False, "has_audible_sound": False, "max_volume_db": -99.0}

        vol_cmd = ["ffmpeg", "-hide_banner", "-i", file_path, "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "-"]
        vol_res = subprocess.run(vol_cmd, capture_output=True, text=True, timeout=15)
        max_vol = -99.0
        for line in vol_res.stderr.splitlines():
            if "max_volume:" in line:
                try:
                    max_vol = float(line.split("max_volume:")[1].split("dB")[0].strip())
                except Exception:
                    pass
        has_audible = max_vol > -45.0
        return {"has_audio": True, "has_audible_sound": has_audible, "max_volume_db": max_vol}
    except Exception as e:
        logger.warning("Could not inspect audio track of %s: %s", file_path, redact(str(e)))
        return {"has_audio": False, "has_audible_sound": False, "max_volume_db": -99.0}


def get_audio_assets_for_topic(topic: str, category: str, mood: str = "calm_ambient",
                               duration: int = 25, override_mode: str = None,
                               video_path: str = None) -> dict:
    """
    Returns audio config according to content context:
    - If category is 'anime_scene' or 'movie_scene' (or override 'original_voice'):
        Preserves original character voices and scene audio at 100% volume; suppresses AI voiceover.
    - If category is 'nature' (or override 'nature_asmr'):
        Uses natural clip sound or realistic ambient soundscape + calm royalty-free music; no AI voiceover.
    - If commentary (facts, stoic, tech, gaming, etc.):
        Uses viral AI script + Edge-TTS voiceover + royalty-free background music; mutes video B-roll.
    """
    mode = override_mode

    if not mode:
        if category in ("anime_scene", "movie_scene"):
            mode = "original_voice"
        elif category == "nature":
            mode = "nature_asmr"
        else:
            # Check if video_path has real audible audio and topic indicates scene/clip
            if video_path and os.path.exists(video_path):
                track_info = check_video_audio_track(video_path)
                if track_info.get("has_audible_sound"):
                    t = (topic or "").lower()
                    if any(w in t for w in ["scene", "clip", "fight", "battle", "voice", "dialogue", "sound"]):
                        mode = "original_voice"
            if not mode:
                mode = "commentary_speech"

    if mode == "original_voice":
        return {
            "mode": "original_voice",
            "voiceover_required": False,
            "use_original_audio": True,
            "video_volume": 1.0,
            "ambient_src": None,
            "ambient_volume": 0.0,
            "music_src": None,
            "music_volume": 0.0,
            "description": "Original scene voice & audio preserved; AI voiceover suppressed.",
        }
    elif mode == "nature_asmr":
        soundscape = get_nature_soundscape(topic, duration)
        soft_music = get_music_track("calm_ambient", duration)
        return {
            "mode": "nature_asmr",
            "voiceover_required": False,
            "use_original_audio": True,
            "video_volume": 0.75,
            "ambient_src": soundscape,
            "ambient_volume": 0.65,
            "music_src": soft_music,
            "music_volume": 0.22,
            "description": "Nature ASMR mode: natural soundscape + relaxing ambient music.",
        }
    else:
        music = get_music_track(mood, duration)
        return {
            "mode": "commentary_speech",
            "voiceover_required": True,
            "use_original_audio": False,
            "video_volume": 0.0,
            "ambient_src": None,
            "ambient_volume": 0.0,
            "music_src": music,
            "music_volume": 0.16,
            "description": "Commentary mode: viral AI script + neural voiceover + royalty-free music.",
        }
