#!/usr/bin/env python3
"""
Metadata Generator Module - AI Shorts Factory
Builds the title, description, hashtags and tags for a Short from its topic (templates, no paid API).
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

TITLE_LIMIT = 100  # YouTube's maximum


def _title_case(topic: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in topic.split())


def generate_metadata(topic: str) -> dict:
    topic = " ".join((topic or "").split())
    if not topic:
        return {"status": "FAILED", "error": "Topic is empty"}

    name = _title_case(topic)
    tag = re.sub(r"\W", "", topic.lower())

    title = f"Relaxing {name} | Calm Vertical View #Shorts"
    if len(title) > TITLE_LIMIT:
        title = f"{name[:TITLE_LIMIT - 8].rstrip()} #Shorts"

    hashtags = ["#shorts"] + ([f"#{tag}"] if tag else []) + ["#relaxing", "#calm"]
    description = (
        f"A calm, vertical look at {topic.lower()}. Take a breath and enjoy.\n\n"
        f"Subscribe for more relaxing Shorts.\n\n"
        f"Footage: free stock video (Pexels / Pixabay).\n\n"
        + " ".join(hashtags)
    )
    tags = list(dict.fromkeys([topic.lower(), "shorts", "relaxing", "calm", "stock footage"]))

    logger.info(f"Generated metadata for topic '{topic}': Title='{title}'")
    return {
        "status": "SUCCESS",
        "topic": topic,
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate YouTube Shorts metadata")
    parser.add_argument("--topic", type=str, default="waterfall", help="Topic for metadata generation")
    parser.add_argument("--output", type=str, default=None, help="Also write the metadata to this JSON file (read by uploader.py --metadata)")
    args = parser.parse_args()

    metadata = generate_metadata(args.topic)
    if metadata["status"] == "SUCCESS" and args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        metadata["output_path"] = args.output
    print(json.dumps(metadata, indent=2))
    if metadata["status"] != "SUCCESS":
        sys.exit(1)


if __name__ == "__main__":
    main()
