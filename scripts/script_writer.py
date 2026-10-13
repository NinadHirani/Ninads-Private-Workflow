#!/usr/bin/env python3
"""
Script Writer - AI Shorts Factory
Generates high-retention, creative commentary scripts tailored to any genre:
Anime, Gaming, Sci-Fi Lore, Mind-Blowing Facts, or Ambient Nature.
Free forever: uses Gemini/Groq LLMs if keys are available, with genre-specific
viral script templates when offline.
"""
import json
import os
import re
import logging
import random

logger = logging.getLogger("script_writer")

MAX_LINES = int(os.getenv("SCRIPT_MAX_LINES", "10"))

GENRE_PROMPTS = {
    "stoic": """You write viral, life-altering Stoic wisdom YouTube Shorts and Instagram Reels scripts.
Topic: {topic}
Format: 4 to 6 punchy, profound spoken sentences (target 18-20 seconds total).
- Line 1 is an electrifying mindset hook (e.g. "Most people realize this truth way too late.").
- Middle lines deliver razor-sharp wisdom on self-mastery, emotional control, or resilience.
- Final line connects seamlessly back into the hook for an infinite loop.
No emojis, no stage directions, deep cinematic spoken English.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]""",

    "tech_ai": """You write viral future tech and AI breakthrough YouTube Shorts and Instagram Reels scripts.
Topic: {topic}
Format: 4 to 6 fast-paced spoken sentences (target 18-20 seconds total).
- Line 1 is a mind-bending hook about a technology that feels illegal or futuristic.
- Middle lines rapidly explain how it works and how it shatters the status quo.
- Final line triggers a debate or infinite loop.
No emojis, no stage directions, conversational spoken English.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]""",

    "facts_mystery": """You write suspenseful, viral mystery and dark psychology YouTube Shorts scripts.
Topic: {topic}
Format: 4 to 6 short spoken sentences (target 18-20 seconds total).
- Line 1 is an irresistible curiosity hook or paradox that stops the scroll instantly.
- Middle lines unfold the unbelievable truth or psychology glitch point by point.
- Final line leaves the viewer stunned and seamlessly loops back to line 1.
No emojis, no stage directions, conversational spoken English.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]""",

    "anime": """You write high-retention viral YouTube Shorts scripts about anime and manga.
Topic: {topic}
Format: 4 to 6 punchy spoken sentences (target 18-20 seconds total).
- Line 1 is an irresistible hook (a bold claim or shocking feat that grabs attention in 2 seconds).
- Middle lines deliver the epic lore or power feats with intense excitement.
- Final line asks who wins or loops back.
No emojis, no stage directions, conversational spoken English.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]""",

    "gaming": """You write high-octane, viral gaming YouTube Shorts scripts.
Topic: {topic}
Format: 4 to 6 punchy spoken sentences (target 18-20 seconds total).
- Line 1 is a bold gaming hook (secret trick, broken mechanic, or impossible feat).
- Middle lines break down what makes this legendary.
- Final line asks gamers for their take.
No emojis, no stage directions.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]""",

    "general": """You write viral vertical video scripts designed for 100%+ retention rate.
Topic: {topic}
Format: 4 to 6 short spoken sentences (target 18-20 seconds total).
- Line 1 is a bold, scroll-stopping hook.
- Middle lines deliver surprising insights.
- Final line loops back into the first sentence.
No emojis, no stage directions.
Respond with ONLY a JSON array of strings, for example: ["line one", "line two"]""",
}



def _clean_lines(text: str) -> list:
    text = re.sub(r"^```(?:json)?\s*|```\s*$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)
    lines = [str(x).strip() for x in (data if isinstance(data, list) else data.get("lines", [])) if str(x).strip()]
    return lines[:MAX_LINES]


def _try_gemini(topic: str, category: str):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    import urllib.request
    prompt_tpl = GENRE_PROMPTS.get(category, GENRE_PROMPTS["general"])
    prompt = prompt_tpl.format(topic=topic, max_lines=MAX_LINES)
    url = ("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + key)
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return _clean_lines(out["candidates"][0]["content"]["parts"][0]["text"])


def _try_groq(topic: str, category: str):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    import urllib.request
    prompt_tpl = GENRE_PROMPTS.get(category, GENRE_PROMPTS["general"])
    prompt = prompt_tpl.format(topic=topic, max_lines=MAX_LINES)
    body = json.dumps({
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
    }).encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return _clean_lines(out["choices"][0]["message"]["content"])


def _genre_templates(topic: str, category: str) -> list:
    t = topic.strip().rstrip(".")
    title_case = t.title()

    if category == "anime":
        return [
            f"Here is the wild reason {title_case} changed anime forever.",
            f"Most shonen heroes train for decades to barely survive their enemies.",
            f"Yet in {title_case}, every single battle ends with pure shock.",
            "The creators threw out every standard rule of powerscaling.",
            "Instead of endless power-ups, we got raw unstoppable dominance.",
            "Fans still debate what would happen if this world collided with other universes.",
            "Because when a single blow can alter the weather, nobody stands a chance.",
            "Who do you think has any hope of surviving this? Tell me in the comments!",
        ]

    if category == "facts_mystery":
        return [
            f"There is a chilling paradox about {title_case} that scientists rarely discuss.",
            "On the surface, everything seems completely ordinary.",
            "Until you look at the raw data beneath reality.",
            "What happened next shattered our traditional understanding.",
            "Every single experiment revealed an impossible contradiction.",
            "And the closer we look, the more mysterious it becomes.",
            "Some believe we were never meant to uncover this truth.",
            "Do you think humanity is ready to understand it?",
        ]

    if category == "gaming":
        return [
            f"This secret feature in {title_case} completely broke the entire game.",
            "For years, players thought they knew every mechanic.",
            "Until one creator discovered an unintended combo.",
            "It bypassed every damage cap in the game engine.",
            "Developers rushed to patch it, but players had already conquered the leaderboard.",
            "Even now, it remains one of the most legendary exploits in gaming history.",
            "Did you ever manage to pull this off back in the day?",
        ]

    if category == "nature":
        return [
            f"Take a deep breath and immerse yourself in {title_case}.",
            "Far away from the noise, the natural world moves in rhythm.",
            "Ancient forces carve through the landscape with timeless patience.",
            "Every droplet, every leaf, tells a story millions of years in the making.",
            "Moments like this remind us of how vast and peaceful the earth truly is.",
            "Pause for ten seconds and let this serenity sink in.",
            "Which place brings you this kind of peace? Save this for your daily calm.",
        ]

    # General default
    return [
        f"Everyone is talking about {title_case}, but almost nobody sees the real picture.",
        f"Here is the exact breakthrough that changed everything.",
        "For years, people assumed this was completely impossible.",
        "Then one radical shift turned the whole system upside down.",
        "And the ones who recognized it early are dominating today.",
        "So what does this actually mean for you?",
        "A huge gap between those who adapt and those who get left behind.",
        "Now you know before the crowd does.",
    ]


def write_script(topic: str, category: str = None) -> dict:
    topic = (topic or "").strip() or "artificial intelligence"
    if not category:
        from scripts.scene_generator import classify_topic
        category = classify_topic(topic).get("category", "general")

    for writer, fn in (("gemini", _try_gemini), ("groq", _try_groq)):
        try:
            lines = fn(topic, category)
            if lines:
                logger.info("Script written with %s (%d lines, category=%s)", writer, len(lines), category)
                return {
                    "status": "SUCCESS",
                    "writer": writer,
                    "category": category,
                    "lines": lines,
                    "caption": topic.upper()[:60],
                }
        except Exception as exc:
            logger.warning("%s failed (%s), trying next writer", writer, exc)

    lines = _genre_templates(topic, category)
    logger.info("Script written with built-in genre template (%d lines, category=%s)", len(lines), category)
    return {
        "status": "SUCCESS",
        "writer": "genre_template",
        "category": category,
        "lines": lines,
        "caption": topic.upper()[:60],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Write a commentary script for a topic")
    parser.add_argument("--topic", type=str, required=True)
    parser.add_argument("--category", type=str, default=None)
    args = parser.parse_args()
    print(json.dumps(write_script(args.topic, args.category), indent=2))


if __name__ == "__main__":
    main()
