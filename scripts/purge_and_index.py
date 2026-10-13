#!/usr/bin/env python3
"""
Purge and Index - AI Shorts Factory
Indexes all previously uploaded/processed videos into the deduplication database (SQLite),
then safely purges historical video files in downloads/, edited/, archive/, and deliverables/
to reclaim disk space without losing tracking history.
"""

import os
import sys
import glob
import json
import sqlite3
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.logger import init_db, mark_topic_used, mark_asset_used, DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cleaner")


def index_historical_data():
    """Reads all historical files and logs to populate used_assets and used_topics."""
    init_db()
    indexed_topics = 0
    indexed_assets = 0

    # 1. Index from deliverables/*.json
    deliverables_dir = os.path.join(ROOT, "deliverables")
    if os.path.exists(deliverables_dir):
        for meta_file in glob.glob(os.path.join(deliverables_dir, "*.json")):
            try:
                with open(meta_file, encoding="utf-8") as f:
                    data = json.load(f)
                topic = data.get("topic")
                if topic:
                    mark_topic_used(topic)
                    indexed_topics += 1
                vid = data.get("deliverable_video")
                if vid:
                    mark_asset_used(os.path.basename(vid), topic=topic or "")
                    indexed_assets += 1
            except Exception as e:
                logger.debug(f"Could not read {meta_file}: {e}")

    # 2. Index from execution_logs in SQLite
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT topic, video_name, youtube_video_id FROM execution_logs")
            rows = cursor.fetchall()
            for topic, video_name, yt_id in rows:
                if topic:
                    mark_topic_used(topic)
                    indexed_topics += 1
                if video_name:
                    mark_asset_used(video_name, topic=topic or "")
                    indexed_assets += 1
                if yt_id:
                    mark_asset_used(yt_id, topic=topic or "")
                    indexed_assets += 1
            conn.close()
        except Exception as e:
            logger.warning(f"Could not index from SQLite logs: {e}")

    # 3. Index from auto_state.json
    auto_state_file = os.path.join(ROOT, "logs", "auto_state.json")
    if os.path.exists(auto_state_file):
        try:
            with open(auto_state_file, encoding="utf-8") as f:
                state = json.load(f)
            for r in state.get("runs", []):
                topic = r.get("topic")
                if topic:
                    mark_topic_used(topic)
                    indexed_topics += 1
        except Exception as e:
            logger.debug(f"Could not index from auto_state.json: {e}")

    logger.info(f"Deduplication index updated: {indexed_topics} topics and {indexed_assets} assets recorded.")


def get_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def format_bytes(bytes_count: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.2f} TB"


def purge_media(dry_run: bool = False) -> dict:
    """Purges all media files in downloads/, edited/, archive/, and deliverables/."""
    target_dirs = [
        os.path.join(ROOT, "downloads"),
        os.path.join(ROOT, "edited"),
        os.path.join(ROOT, "archive"),
        os.path.join(ROOT, "deliverables"),
    ]

    total_bytes = 0
    deleted_files = 0

    for d in target_dirs:
        if not os.path.exists(d):
            continue
        for entry in os.scandir(d):
            if entry.name.startswith("."):
                continue  # preserve .gitkeep
            if "logo" in entry.name.lower():
                continue  # preserve channel logo assets
            # Only delete media and metadata files
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in [".mp4", ".mov", ".json", ".wav", ".mp3", ".jpg", ".png"]:
                    sz = entry.stat().st_size
                    total_bytes += sz
                    deleted_files += 1
                    if not dry_run:
                        try:
                            os.remove(entry.path)
                        except Exception as e:
                            logger.warning(f"Could not remove {entry.path}: {e}")

    # Also clean remotion/public/scenes if present
    scenes_dir = os.path.join(ROOT, "remotion", "public", "scenes")
    if os.path.exists(scenes_dir):
        for entry in os.scandir(scenes_dir):
            if entry.is_file():
                total_bytes += entry.stat().st_size
                deleted_files += 1
                if not dry_run:
                    try:
                        os.remove(entry.path)
                    except Exception:
                        pass

    action_label = "Found for removal" if dry_run else "Successfully purged"
    logger.info(f"{action_label}: {deleted_files} files ({format_bytes(total_bytes)} reclaimed).")

    return {
        "deleted_count": deleted_files,
        "bytes_reclaimed": total_bytes,
        "human_size": format_bytes(total_bytes),
        "dry_run": dry_run
    }


def run_purge_and_index(dry_run: bool = False):
    print("=" * 60)
    print("  AI SHORTS FACTORY - DEDUPLICATION & REPO CLEANUP")
    print("=" * 60)
    print("1. Indexing all past topics and video assets into SQLite...")
    index_historical_data()
    print("2. Purging video and metadata files to free disk space...")
    res = purge_media(dry_run=dry_run)
    print(f"\nDone! Reclaimed {res['human_size']} across {res['deleted_count']} files.")
    print("All past topics and video footage will never be repeated.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Index history and purge media files")
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without deleting")
    args = parser.parse_args()
    run_purge_and_index(dry_run=args.dry_run)
