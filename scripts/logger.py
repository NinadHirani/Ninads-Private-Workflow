#!/usr/bin/env python3
"""
Logger Module - AI Shorts Factory
Logs execution details to SQLite database logs/history.db and CSV logs/execution.csv
"""

import os
import sys
import csv
import json
import sqlite3
import datetime
import argparse
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("logger_module")

LOG_DIR = os.getenv("LOG_PATH", "logs")
DB_PATH = os.path.join(LOG_DIR, "history.db")
CSV_PATH = os.path.join(LOG_DIR, "execution.csv")

def init_db():
    os.makedirs(LOG_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            topic TEXT,
            status TEXT,
            video_name TEXT,
            youtube_video_id TEXT,
            youtube_url TEXT,
            execution_time_sec REAL,
            retry_count INTEGER,
            error_message TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT UNIQUE,
            provider TEXT,
            topic TEXT,
            used_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_normalized TEXT UNIQUE,
            original_topic TEXT,
            used_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def mark_asset_used(asset_id: str, provider: str = "", topic: str = "") -> bool:
    if not asset_id:
        return False
    init_db()
    now = datetime.datetime.now().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO used_assets (asset_id, provider, topic, used_at)
            VALUES (?, ?, ?, ?)
        ''', (str(asset_id), provider, topic, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to record used asset {asset_id}: {e}")
        return False

def is_asset_used(asset_id: str) -> bool:
    if not asset_id:
        return False
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM used_assets WHERE asset_id = ?', (str(asset_id),))
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        logger.error(f"Failed to check used asset {asset_id}: {e}")
        return False

def get_used_asset_ids() -> set:
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT asset_id FROM used_assets')
        rows = cursor.fetchall()
        conn.close()
        return {r[0] for r in rows if r[0]}
    except Exception as e:
        logger.error(f"Failed to get used asset IDs: {e}")
        return set()

def normalize_topic(topic: str) -> str:
    import re
    cleaned = re.sub(r'[^a-z0-9]+', ' ', (topic or '').lower()).strip()
    return cleaned

def mark_topic_used(topic: str) -> bool:
    if not topic:
        return False
    init_db()
    norm = normalize_topic(topic)
    if not norm:
        return False
    now = datetime.datetime.now().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO used_topics (topic_normalized, original_topic, used_at)
            VALUES (?, ?, ?)
        ''', (norm, topic.strip(), now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to mark topic used {topic}: {e}")
        return False

def is_topic_used(topic: str) -> bool:
    if not topic:
        return False
    init_db()
    norm = normalize_topic(topic)
    if not norm:
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM used_topics WHERE topic_normalized = ?', (norm,))
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        logger.error(f"Failed to check used topic {topic}: {e}")
        return False

def get_used_topics() -> set:
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT topic_normalized FROM used_topics')
        rows = cursor.fetchall()
        conn.close()
        return {r[0] for r in rows if r[0]}
    except Exception as e:
        logger.error(f"Failed to get used topics: {e}")
        return set()

def log_execution(
    topic: str,
    status: str,
    video_name: str = "",
    youtube_video_id: str = "",
    youtube_url: str = "",
    execution_time_sec: float = 0.0,
    retry_count: int = 0,
    error_message: str = ""
) -> dict:
    init_db()
    timestamp = datetime.datetime.now().isoformat()
    
    # Log to SQLite DB
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO execution_logs 
            (timestamp, topic, status, video_name, youtube_video_id, youtube_url, execution_time_sec, retry_count, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, topic, status, video_name, youtube_video_id, youtube_url, execution_time_sec, retry_count, error_message))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log to SQLite: {e}")
        
    # Log to CSV
    try:
        file_exists = os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Topic", "Status", "VideoName", "YouTubeID", "YouTubeURL", "DurationSec", "Retries", "Error"])
            writer.writerow([timestamp, topic, status, video_name, youtube_video_id, youtube_url, execution_time_sec, retry_count, error_message])
    except Exception as e:
        logger.error(f"Failed to log to CSV: {e}")
        
    logger.info(f"Log entry recorded: Topic='{topic}', Status='{status}', Video='{video_name}', ID='{youtube_video_id}'")
    return {
        "status": "SUCCESS",
        "logged_at": timestamp,
        "topic": topic,
        "execution_status": status
    }

def main():
    parser = argparse.ArgumentParser(description="Log AI Shorts Factory execution history")
    parser.add_argument("--topic", type=str, default="waterfall", help="Content topic")
    parser.add_argument("--status", type=str, default="SUCCESS", help="Execution status (SUCCESS/FAILED)")
    parser.add_argument("--video", type=str, default="", help="Video filename")
    parser.add_argument("--yt_id", type=str, default="", help="YouTube Video ID")
    parser.add_argument("--yt_url", type=str, default="", help="YouTube Video URL")
    parser.add_argument("--duration", type=float, default=0.0, help="Execution duration in seconds")
    parser.add_argument("--retries", type=int, default=0, help="Retry count")
    parser.add_argument("--error", type=str, default="", help="Error message if any")
    args = parser.parse_args()
    
    res = log_execution(
        topic=args.topic,
        status=args.status,
        video_name=args.video,
        youtube_video_id=args.yt_id,
        youtube_url=args.yt_url,
        execution_time_sec=args.duration,
        retry_count=args.retries,
        error_message=args.error
    )
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
