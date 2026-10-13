#!/usr/bin/env python3
"""
Metadata Generator Module - AI Shorts Factory
Builds high-CTR title, description, hashtags and tags for YouTube Shorts and Instagram Reels,
tailored to the detected topic genre (Anime, Gaming, Sci-Fi Lore, Mystery Facts, Nature).
"""

import os
import re
import sys
import json
import argparse
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("metadata_generator")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TITLE_LIMIT = 100


def _title_case(topic: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in topic.split())


def generate_metadata(topic: str, category: str = None) -> dict:
    topic = " ".join((topic or "").split())
    if not topic:
        return {"status": "FAILED", "error": "Topic is empty"}

    if not category:
        try:
            from scripts.scene_generator import classify_topic
        except ImportError:
            from scene_generator import classify_topic
        category = classify_topic(topic).get("category", "general")

    name = _title_case(topic)
    tag = re.sub(r"\W", "", topic.lower())

    if category == "anime_scene":
        title = f"{name} | Epic Scene (Original Audio) #Shorts"
        hashtags = ["#shorts", "#anime", f"#{tag}", "#animescene", "#originalsound", "#viral"]
        description = (
            f"Witness this iconic moment from {topic}. Preserved with original character voice & scene audio.\n\n"
            f"Subscribe for more epic anime moments and scenes!\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "anime", "anime scene", "original voice", "shorts", "shonen", "viral"]

    elif category in ("movie", "movie_scene"):
        title = f"{name} | Iconic Movie Scene #Shorts"
        hashtags = ["#shorts", "#movies", "#cinema", f"#{tag}", "#moviescene", "#viral"]
        description = (
            f"Iconic cinema moment: {topic}. Preserved in original sound.\n\n"
            f"Subscribe for more legendary movie scenes and moments!\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "movie", "movie scene", "cinema", "shorts", "hollywood", "viral"]

    elif category == "anime":
        titles = [
            f"The Wild Truth About {name} #Shorts",
            f"Why {name} Broke Anime Rules #Shorts",
            f"{name} Explained In 45 Seconds #Shorts",
        ]
        title = titles[0]
        hashtags = ["#shorts", "#anime", f"#{tag}", "#manga", "#animelore", "#viral"]
        description = (
            f"An epic breakdown of {topic}. Did you know this about {name}?\n\n"
            f"Subscribe for more daily anime breakdowns & lore shorts!\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "anime", "manga", "shorts", "anime lore", "shonen", "viral"]

    elif category == "gaming":
        title = f"{name} Secrets That Changed The Game #Shorts"
        hashtags = ["#shorts", "#gaming", f"#{tag}", "#gamer", "#gametok", "#viral"]
        description = (
            f"The secret behind {topic} that every gamer needs to know.\n\n"
            f"Subscribe for daily gaming moments & secret mechanics!\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "gaming", "games", "shorts", "secrets", "lore", "gamer"]

    elif category == "facts_mystery" or category == "scifi_lore":
        title = f"The Mind-Blowing Paradox of {name} #Shorts"
        hashtags = ["#shorts", "#facts", "#mystery", f"#{tag}", "#science", "#mindblowing"]
        description = (
            f"The bizarre truth about {topic} that science rarely explains.\n\n"
            f"Subscribe for daily mind-bending facts & cosmic mysteries!\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "facts", "mystery", "shorts", "science", "space", "unsolved"]

    elif category == "nature":
        title = f"Relaxing {name} | Calm Vertical View #Shorts"
        hashtags = ["#shorts", f"#{tag}", "#relaxing", "#calm", "#nature"]
        description = (
            f"A calm, vertical look at {topic.lower()}. Take a breath and enjoy.\n\n"
            f"Subscribe for more relaxing Shorts.\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "shorts", "relaxing", "calm", "nature", "stock footage"]

    else:
        title = f"{name} - What Nobody Told You #Shorts"
        hashtags = ["#shorts", f"#{tag}", "#insights", "#story", "#viral"]
        description = (
            f"Here is what you need to know about {topic}.\n\n"
            f"Subscribe for more quick breakdowns!\n\n"
            + " ".join(hashtags)
        )
        tags = [topic.lower(), "shorts", "insights", "story", "viral"]

    if len(title) > TITLE_LIMIT:
        title = f"{name[:TITLE_LIMIT - 8].rstrip()} #Shorts"

    logger.info("Generated metadata for topic '%s' (%s): Title='%s'", topic, category, title)
    return {
        "status": "SUCCESS",
        "topic": topic,
        "category": category,
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": list(dict.fromkeys(tags)),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate YouTube Shorts metadata")
    parser.add_argument("--topic", type=str, default="one-punch man anime")
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--output", type=str, default=None, help="Path to write JSON metadata file")
    args = parser.parse_args()
    res = generate_metadata(args.topic, args.category)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
