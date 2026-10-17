#!/usr/bin/env python3
"""
Script Writer - AI Shorts Factory
Generates high-retention, creative commentary scripts tailored to any genre & topic.
Uses dynamic storytelling archetypes, emotional tone modulation, duration-scaled pacing,
and multi-tier LLM generation (Gemini, Groq, Pollinations free text) with an offline
combinatorial procedural generator.
"""
import json
import os
import re
import logging
import random
import urllib.request
import urllib.parse

try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text):
            return text

try:
    from scripts.script_archetypes import (
        ARCHETYPES,
        EMOTIONAL_TONES,
        auto_select_matrix,
        build_system_prompt,
        generate_combinatorial_script,
        calculate_pacing_targets
    )
except ImportError:
    from script_archetypes import (
        ARCHETYPES,
        EMOTIONAL_TONES,
        auto_select_matrix,
        build_system_prompt,
        generate_combinatorial_script,
        calculate_pacing_targets
    )

logger = logging.getLogger("script_writer")

MAX_LINES = int(os.getenv("SCRIPT_MAX_LINES", "12"))

# Kept for backward compatibility
GENRE_PROMPTS = {
    "general": """You write viral vertical video scripts designed for 100%+ retention rate.
Topic: {topic}
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]"""
}


def _clean_lines(text: str, max_lines: int = MAX_LINES) -> list:
    """Robustly extracts script sentences from LLM response (JSON array, dict, or line list)."""
    if not text:
        return []

    cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", text.strip(), flags=re.M).strip()

    # Attempt 1: Direct JSON parsing
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            lines = [str(x).strip() for x in data if str(x).strip()]
            if lines:
                return lines[:max_lines]
        elif isinstance(data, dict):
            raw = data.get("lines") or data.get("script") or list(data.values())
            if isinstance(raw, list):
                lines = [str(x).strip() for x in raw if str(x).strip()]
                if lines:
                    return lines[:max_lines]
    except Exception:
        pass

    # Attempt 2: Extract JSON array with regex
    match = re.search(r'\[\s*".*?"\s*\]', cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()][:max_lines]
        except Exception:
            pass

    # Attempt 3: Line-by-line fallback (bullet points, numbered lines)
    raw_lines = cleaned.splitlines()
    lines = []
    for line in raw_lines:
        line = re.sub(r'^(?:\d+[\.\)]|\-|\*)\s*', '', line.strip()).strip(' "\'')
        if line and len(line) > 10:
            lines.append(line)

    if lines:
        return lines[:max_lines]

    # Attempt 4: Sentence splitting
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 10]
    return sentences[:max_lines]


def _try_gemini(topic: str, category: str = "general", prompt: str = None):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    if not prompt:
        prompt = build_system_prompt(topic, "narrative_story", "awe_inspiring", 45, "english")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return _clean_lines(out["candidates"][0]["content"]["parts"][0]["text"])


def _try_groq(topic: str, category: str = "general", prompt: str = None):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    if not prompt:
        prompt = build_system_prompt(topic, "narrative_story", "awe_inspiring", 45, "english")
    body = json.dumps({
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return _clean_lines(out["choices"][0]["message"]["content"])


def _try_pollinations(topic: str, category: str = "general", prompt: str = None):
    """Free online AI text generation fallback without requiring any API keys."""
    if os.getenv("SHORTS_MOCK") == "1":
        return None
    if not prompt:
        prompt = build_system_prompt(topic, "narrative_story", "awe_inspiring", 45, "english")
    try:
        url = "https://text.pollinations.ai/"
        body = json.dumps({
            "messages": [
                {"role": "system", "content": "You are a viral YouTube Shorts script writer. Return ONLY a raw JSON array of strings, without markdown backticks or conversational filler."},
                {"role": "user", "content": prompt}
            ],
            "model": "openai-fast"
        }).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "AI-Shorts-Factory/1.0"}
        )
        with urllib.request.urlopen(req, timeout=18) as resp:
            text = resp.read().decode("utf-8")
        return _clean_lines(text)
    except Exception as exc:
        logger.debug("Pollinations text API unavailable: %s", redact(str(exc)))
        return None


def write_script(
    topic: str,
    category: str = None,
    duration: int = 45,
    archetype: str = None,
    emotion: str = None,
    language: str = None
) -> dict:
    """
    Writes a viral commentary script using dynamic storytelling archetypes and emotions.
    Automatically resolves missing parameters using the intelligent auto-selection matrix.
    """
    topic = (topic or "").strip() or "artificial intelligence"

    if not category:
        try:
            from scripts.scene_generator import classify_topic
            category = classify_topic(topic).get("category", "general")
        except Exception:
            category = "general"

    # Intelligent Auto-Selection if archetype / emotion / language not explicitly specified
    matrix = auto_select_matrix(topic, category)
    archetype = archetype or matrix["archetype"]
    emotion = emotion or matrix["emotion"]
    language = language or matrix["language"]

    prompt = build_system_prompt(
        topic=topic,
        archetype_key=archetype,
        emotion_key=emotion,
        duration=duration,
        language=language
    )

    # Multi-Tier LLM Generation Chain
    writers = [("gemini", _try_gemini), ("groq", _try_groq)]
    if os.getenv("USE_POLLINATIONS_TEXT", "1") == "1" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")):
        writers.append(("pollinations", _try_pollinations))

    for writer_name, fn in writers:
        try:
            try:
                lines = fn(topic, category, prompt=prompt)
            except TypeError:
                lines = fn(topic, category)

            if lines and len(lines) >= 3:
                logger.info(
                    "Script written with %s (%d lines, archetype=%s, emotion=%s, lang=%s)",
                    writer_name, len(lines), archetype, emotion, language
                )
                return {
                    "status": "SUCCESS",
                    "writer": writer_name,
                    "category": category,
                    "archetype": archetype,
                    "emotion": emotion,
                    "language": language,
                    "lines": lines,
                    "caption": topic.upper()[:60],
                }
        except Exception as exc:
            logger.warning("%s failed (%s), trying next writer", writer_name, redact(str(exc)))

    # Offline Procedural Fallback (Combinatorial sentence banks)
    lines = generate_combinatorial_script(
        topic=topic,
        archetype=archetype,
        duration=duration,
        language=language
    )
    logger.info(
        "Script written with procedural combinatorial generator (%d lines, archetype=%s, emotion=%s)",
        len(lines), archetype, emotion
    )
    return {
        "status": "SUCCESS",
        "writer": "genre_template",
        "category": category,
        "archetype": archetype,
        "emotion": emotion,
        "language": language,
        "lines": lines,
        "caption": topic.upper()[:60],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Write a dynamic commentary script for a topic")
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--duration", type=int, default=45)
    parser.add_argument("--archetype", type=str, default=None)
    parser.add_argument("--emotion", type=str, default=None)
    parser.add_argument("--language", type=str, default=None)
    args = parser.parse_args()
    print(json.dumps(write_script(
        topic=args.topic,
        category=args.category,
        duration=args.duration,
        archetype=args.archetype,
        emotion=args.emotion,
        language=args.language
    ), indent=2))


if __name__ == "__main__":
    main()
