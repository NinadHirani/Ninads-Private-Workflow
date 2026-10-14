#!/usr/bin/env python3
"""
Voiceover - AI Shorts Factory
Script lines -> spoken audio + word-level timings. Free forever.
Primary: Microsoft Edge neural voices through edge-tts (free, no key, internet).
Fallback: Piper local neural voice (fully offline) aligned with faster-whisper,
with a one-time free voice model download.
"""
import math
import os
import re
import sys
import shutil
import time
import logging
import subprocess
import tempfile
import urllib.request

logger = logging.getLogger("voiceover")

VOICES_FALLBACK = [
    os.getenv("VOICEOVER_VOICE", "en-US-BrianNeural"),
    "en-US-ChristopherNeural",
    "en-US-GuyNeural",
    "en-US-EricNeural",
]
PIPER_MODEL = os.getenv("PIPER_MODEL", "")
PIPER_DIR = os.getenv("PIPER_DIR", os.path.join(tempfile.gettempdir(), "piper-voices"))
PIPER_VOICE_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                   "en/en_US/lessac/medium/en_US-lessac-medium")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
MAX_RETRY_DELAY_SECONDS = 60.0  # hard cap on any single edge-tts retry wait


def _bounded_int_env(name: str, default: int, low: int, high: int) -> int:
    """Read an int env var safely: invalid values fall back to the default, others are clamped."""
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; using default %d", name, raw, default)
        return default
    if value < low or value > high:
        logger.warning("%s=%d is outside %d..%d; clamping", name, value, low, high)
        return min(high, max(low, value))
    return value


def _bounded_float_env(name: str, default: float, low: float, high: float) -> float:
    """Read a float env var safely: invalid values fall back to the default, others are clamped."""
    raw = (os.getenv(name) or "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; using default %g", name, raw, default)
        return default
    if not math.isfinite(value):
        logger.warning("Invalid %s=%r (non-finite); using default %g", name, raw, default)
        return default
    if value < low or value > high:
        logger.warning("%s=%g is outside %g..%g; clamping", name, value, low, high)
        return min(high, max(low, value))
    return value


def _remove_quietly(path: str) -> None:
    """Delete an intermediate file if it exists; a cleanup failure never breaks the pipeline."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        logger.debug("Could not remove intermediate file %s", path)


def make_voiceover(lines: list, out_dir: str) -> dict:
    text = " ".join(str(l).strip() for l in lines if str(l).strip())
    if not text:
        return {"status": "FAILED", "error": "empty script"}
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, "voiceover.wav")

    # 1. Primary: edge-tts with retry & voice rotation.
    # A single 403 is often transient, so each voice gets EDGE_TTS_ATTEMPTS tries
    # with exponential backoff before rotating to the next voice.
    attempts_per_voice = _bounded_int_env("EDGE_TTS_ATTEMPTS", 2, 1, 10)
    base_backoff = _bounded_float_env("EDGE_TTS_BACKOFF_SECONDS", 2.0, 0.0, 60.0)
    for voice_name in VOICES_FALLBACK:
        for attempt in range(attempts_per_voice):
            try:
                words = _edge(text, out_dir, wav, voice=voice_name)
                logger.info("Voiceover made with edge-tts (%s, %d words)", voice_name, len(words or []))
                return {"status": "SUCCESS", "voice": f"edge-tts:{voice_name}", "file": wav, "words": words, "text": text}
            except Exception as exc:
                if attempt + 1 < attempts_per_voice:
                    delay = min(base_backoff * (2 ** attempt), MAX_RETRY_DELAY_SECONDS)
                    logger.warning("edge-tts failed on attempt %d/%d (%s) with voice %s; retrying in %.0fs",
                                   attempt + 1, attempts_per_voice, exc, voice_name, delay)
                    time.sleep(delay)
                else:
                    logger.warning("edge-tts failed on attempt %d/%d (%s) with voice %s; trying next voice",
                                   attempt + 1, attempts_per_voice, exc, voice_name)
                    time.sleep(1.0)

    # 2. Fallback: macOS say (if available on macOS)
    if shutil.which("say"):
        try:
            words = _macos_say(text, out_dir, wav)
            logger.info("Voiceover made with macOS say fallback")
            return {"status": "SUCCESS", "voice": "macos-say", "file": wav, "words": words, "text": text}
        except Exception as exc:
            logger.warning("macOS say failed (%s); trying Piper if installed", exc)

    # 3. Fallback: Piper local neural voice (only if piper is actually installed)
    if _piper_available():
        try:
            words = _piper(text, wav)
            logger.info("Voiceover made with Piper (%d words)", len(words or []))
            return {"status": "SUCCESS", "voice": "piper", "file": wav, "words": words, "text": text}
        except Exception as exc:
            logger.warning("Piper failed: %s", exc)

    return {"status": "FAILED", "error": "all TTS methods failed (edge-tts, say, piper)"}


def _piper_available() -> bool:
    if shutil.which("piper"):
        return True
    try:
        py = _get_python()
        res = subprocess.run([py, "-c", "import piper"], capture_output=True)
        return res.returncode == 0
    except Exception:
        return False


def _macos_say(text: str, out_dir: str, wav: str) -> list:
    aiff = os.path.join(out_dir, "vo.aiff")
    try:
        subprocess.run(["say", "-o", aiff, text], check=True, timeout=60)
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", aiff,
                        "-ar", "44100", "-ac", "2", wav], check=True, capture_output=True)
        return []
    finally:
        # the intermediate aiff is removed on success AND on failure
        _remove_quietly(aiff)


def _get_python():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_py = os.path.join(root, ".venv", "bin", "python")
    return venv_py if os.path.exists(venv_py) else sys.executable


def _edge(text: str, out_dir: str, wav: str, voice: str = None) -> list:
    mp3 = os.path.join(out_dir, "vo.mp3")
    vtt = os.path.join(out_dir, "vo.vtt")
    try:
        py = _get_python()
        target_voice = voice or VOICES_FALLBACK[0]
        subprocess.run([py, "-m", "edge_tts", "--voice", target_voice, "--text", text,
                        "--write-media", mp3, "--write-subtitles", vtt],
                       check=True, capture_output=True, timeout=120)
        words = _parse_vtt(vtt)
        if not os.path.exists(mp3) or os.path.getsize(mp3) == 0:
            raise RuntimeError("edge-tts produced no audio")
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", mp3,
                        "-ar", "44100", "-ac", "2", wav], check=True, capture_output=True)
        return words
    finally:
        # intermediates (raw mp3 + vtt) are removed on success AND on failure,
        # so a failed attempt never leaves partial vo.mp3/vo.vtt behind
        _remove_quietly(mp3)
        _remove_quietly(vtt)


def _parse_vtt(path: str) -> list:
    words = []
    timing = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)\s*-->\s*(\d+):(\d+):(\d+)[.,](\d+)")
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    i = 0
    while i < len(lines):
        m = timing.search(lines[i])
        if m:
            h, mi, s, ms, h2, mi2, s2, ms2 = (int(x) for x in m.groups())
            start = h * 3600 + mi * 60 + s + ms / 1000.0
            end = h2 * 3600 + mi2 * 60 + s2 + ms2 / 1000.0
            for j in range(i + 1, min(i + 4, len(lines))):
                txt = lines[j].strip()
                if txt and "-->" not in txt and not txt.isdigit():
                    cue_words = txt.split()
                    if cue_words:
                        dur_per_word = (end - start) / len(cue_words)
                        for k, w in enumerate(cue_words):
                            w_st = round(start + k * dur_per_word, 2)
                            w_en = round(start + (k + 1) * dur_per_word, 2)
                            words.append({"word": w, "start": w_st, "end": w_en})
                    break
            i += 2
        else:
            i += 1
    return words


def _piper(text: str, wav: str) -> list:
    model = PIPER_MODEL or _ensure_piper_model()
    subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", wav],
                   input=text.encode(), check=True, capture_output=True, timeout=300)
    if not os.path.exists(wav) or os.path.getsize(wav) == 0:
        raise RuntimeError("Piper produced no audio")
    return _align(wav, text)


def _ensure_piper_model() -> str:
    for candidate in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "assets", "voice", "en_US-lessac-medium.onnx"),
                      os.path.join(PIPER_DIR, "en_US-lessac-medium.onnx")):
        if os.path.exists(candidate):
            return candidate
    os.makedirs(PIPER_DIR, exist_ok=True)
    for suffix in (".onnx", ".onnx.json"):
        dest = os.path.join(PIPER_DIR, "en_US-lessac-medium" + suffix)
        logger.info("Downloading Piper voice model%s (one-time, free)", suffix)
        urllib.request.urlretrieve(PIPER_VOICE_URL + suffix, dest)
    return os.path.join(PIPER_DIR, "en_US-lessac-medium.onnx")


def _align(wav: str, text: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("faster-whisper not installed; captions fall back to sentence timing")
        return None
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(wav, word_timestamps=True)
    words = []
    for seg in segments:
        for w in seg.words:
            token = (w.word or "").strip()
            if token:
                words.append((token, round(w.start, 2), round(w.end, 2)))
    return words


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Make a voiceover with word timings")
    parser.add_argument("--lines", type=str, required=True, help="JSON list of lines")
    parser.add_argument("--out-dir", type=str, default=".")
    args = parser.parse_args()
    import json
    result = make_voiceover(json.loads(args.lines), args.out_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
