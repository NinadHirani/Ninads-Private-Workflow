#!/usr/bin/env python3
"""
Script Writer - AI Shorts Factory
Turns a topic into a short commentary script: a hook, punchy body lines, a takeaway.
Free forever: uses a free-tier LLM key if one is set (GEMINI_API_KEY or GROQ_API_KEY),
otherwise falls back to a built-in template so the factory never stalls offline.
"""
import json
import os
import re
import logging

logger = logging.getLogger("script_writer")

MAX_LINES = int(os.getenv("SCRIPT_MAX_LINES", "10"))

PROMPT = """You write scripts for 45-60 second vertical video commentary reels.
Topic: {topic}
Write 8 to {max_lines} short spoken lines. Line 1 is a hook (a bold claim or question).
The middle lines deliver the story or argument, one surprising point each, no repetition.
The final line is a punchy takeaway. Conversational, no emoji, no hashtags, no stage directions.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]"""


def _clean_lines(text: str) -> list:
    text = re.sub(r"^```(?:json)?\s*|```\s*$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)
    lines = [str(x).strip() for x in (data if isinstance(data, list) else data.get("lines", [])) if str(x).strip()]
    return lines[:MAX_LINES]


def _try_gemini(topic: str):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    import urllib.request
    url = ("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + key)
    body = json.dumps({"contents": [{"parts": [{"text": PROMPT.format(topic=topic, max_lines=MAX_LINES)}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return _clean_lines(out["candidates"][0]["content"]["parts"][0]["text"])


def _try_groq(topic: str):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    import urllib.request
    body = json.dumps({
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{"role": "user", "content": PROMPT.format(topic=topic, max_lines=MAX_LINES)}],
        "temperature": 0.8,
    }).encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return _clean_lines(out["choices"][0]["message"]["content"])


def _template(topic: str) -> list:
    t = topic.strip().rstrip(".")
    tl = t.lower()
    return [
        f"Everyone is talking about {tl}. But almost nobody explains it this simply.",
        f"Here is the thing about {tl} that changed everything.",
        f"For years, the plan around {tl} looked obvious. It was not.",
        "Then one shift flipped the whole picture.",
        "And the people who saw it early are the ones ahead today.",
        f"So what does {tl} actually mean for you?",
        "Two things: what it replaces, and what it makes possible.",
        "The first one everyone fears. The second one almost no one acts on.",
        f"That gap is where the whole story of {tl} is heading.",
        "Now you know before the crowd does.",
    ]


def write_script(topic: str) -> dict:
    topic = (topic or "").strip() or "artificial intelligence"
    for writer, fn in (("gemini", _try_gemini), ("groq", _try_groq)):
        try:
            lines = fn(topic)
            if lines:
                logger.info("Script written with %s (%d lines)", writer, len(lines))
                return {"status": "SUCCESS", "writer": writer, "lines": lines,
                        "caption": topic.upper()[:60]}
        except Exception as exc:
            logger.warning("%s failed (%s), trying next writer", writer, exc)
    lines = _template(topic)
    logger.info("Script written with built-in template (%d lines)", len(lines))
    return {"status": "SUCCESS", "writer": "template", "lines": lines,
            "caption": topic.upper()[:60]}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Write a commentary script for a topic")
    parser.add_argument("--topic", type=str, required=True)
    args = parser.parse_args()
    print(json.dumps(write_script(args.topic), indent=2))


if __name__ == "__main__":
    main()
