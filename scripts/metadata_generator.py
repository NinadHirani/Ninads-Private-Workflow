#!/usr/bin/env python3
"""
Metadata Generator Module - AI Shorts Factory
Generates SEO optimized title, description, and hashtags for YouTube Shorts.
"""

import os
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

def generate_metadata(topic: str) -> dict:
    topic_clean = topic.strip().capitalize()
    
    # Template-based metadata generation
    title = f"Stunning {topic_clean} Relaxation | Beautiful Nature #Shorts"
    if len(title) > 95:
        title = title[:95]
        
    description = (
        f"Relax and immerse yourself in this breathtaking vertical view of {topic_clean.lower()}.\n\n"
        f"Subscribe for daily relaxing nature shorts and calming views!\n\n"
        f"#shorts #{topic_clean.lower().replace(' ', '')} #nature #relaxation #viral"
    )
    
    hashtags = ["#shorts", f"#{topic_clean.lower().replace(' ', '')}", "#nature", "#calm", "#relaxation"]
    
    logger.info(f"Generated metadata for topic '{topic}': Title='{title}'")
    
    return {
        "status": "SUCCESS",
        "topic": topic,
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": [topic_clean.lower(), "nature", "shorts", "relaxation", "hd video"]
    }

def main():
    parser = argparse.ArgumentParser(description="Generate YouTube Shorts metadata")
    parser.add_argument("--topic", type=str, default="waterfall", help="Topic for metadata generation")
    args = parser.parse_args()
    
    metadata = generate_metadata(args.topic)
    print(json.dumps(metadata, indent=2))

if __name__ == "__main__":
    main()
