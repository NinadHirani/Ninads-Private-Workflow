#!/usr/bin/env python3
"""
Archive Module - AI Shorts Factory
Moves processed raw and edited videos into archive/ directory safely without overwriting.
"""

import os
import sys
import shutil
import json
import datetime
import argparse
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("archiver")

ARCHIVE_DIR = os.getenv("ARCHIVE_PATH", "archive")

def archive_file(file_path: str) -> str:
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"File for archiving does not exist: {file_path}")
        return None
        
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    base_name = os.path.basename(file_path)
    dest_path = os.path.join(ARCHIVE_DIR, base_name)
    
    # Avoid overwriting existing files
    if os.path.exists(dest_path):
        name, ext = os.path.splitext(base_name)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = os.path.join(ARCHIVE_DIR, f"{name}_{timestamp}{ext}")
        
    shutil.move(file_path, dest_path)
    logger.info(f"Archived '{file_path}' -> '{dest_path}'")
    return dest_path

def cleanup_files(*paths) -> list:
    """Safely removes specified files and directories if they exist."""
    deleted = []
    for p in paths:
        if not p:
            continue
        if isinstance(p, (list, tuple, set)):
            for sub in p:
                deleted.extend(cleanup_files(sub))
            continue
        if os.path.isfile(p):
            try:
                os.remove(p)
                logger.info(f"Cleaned up file: '{p}'")
                deleted.append(p)
            except Exception as e:
                logger.warning(f"Could not delete '{p}': {e}")
        elif os.path.isdir(p):
            try:
                shutil.rmtree(p, ignore_errors=True)
                logger.info(f"Cleaned up directory: '{p}'")
                deleted.append(p)
            except Exception as e:
                logger.warning(f"Could not delete directory '{p}': {e}")
    return deleted

def delete_processed_media(raw_path: str = None, edited_path: str = None,
                           deliverable_video: str = None, deliverable_meta: str = None,
                           workdir: str = None, extra_files: list = None) -> dict:
    """Deletes temporary and uploaded media assets to keep the repo clean."""
    deleted = cleanup_files(raw_path, edited_path, deliverable_video, deliverable_meta, workdir, extra_files)
    return {
        "status": "SUCCESS",
        "deleted_count": len(deleted),
        "deleted_paths": deleted
    }

def archive_processed_media(raw_path: str = None, edited_path: str = None) -> dict:
    archived_raw = archive_file(raw_path) if raw_path else None
    archived_edited = archive_file(edited_path) if edited_path else None
    
    return {
        "status": "SUCCESS",
        "archived_raw": archived_raw,
        "archived_edited": archived_edited
    }

def main():
    parser = argparse.ArgumentParser(description="Archive processed video files")
    parser.add_argument("--raw", type=str, default=None, help="Path to raw video")
    parser.add_argument("--edited", type=str, default=None, help="Path to edited video")
    args = parser.parse_args()
    
    res = archive_processed_media(args.raw, args.edited)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
