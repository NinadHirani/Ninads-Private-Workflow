#!/usr/bin/env python3
"""
Auto Run - AI Shorts Factory
The continuous maker behind `shortsctl start`. Reads context.json, then keeps
making and uploading Shorts (private by default) until a STOP file appears in
logs/ or the process is killed. One Short at a time, state in logs/auto_state.json.
"""

import os
import sys
import json
import time
import signal
import random
import argparse
import logging
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.run_pipeline import run  # noqa: E402

LOG_DIR = os.path.join(ROOT, os.getenv("LOG_PATH", "logs"))
STOP_FILE = os.path.join(LOG_DIR, "STOP")
STATE_FILE = os.path.join(LOG_DIR, "auto_state.json")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("auto_run")

import atexit

STOP_REQUESTED = False


def _cleanup():
    pid_file = os.path.join(LOG_DIR, "auto.pid")
    try:
        if os.path.exists(pid_file):
            with open(pid_file, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("pid") == os.getpid():
                os.remove(pid_file)
    except Exception:
        pass


atexit.register(_cleanup)


def _handle(sig, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    logger.info("Termination signal received (%s). Exiting maker...", sig)
    sys.exit(0)


signal.signal(signal.SIGTERM, _handle)
signal.signal(signal.SIGINT, _handle)


def stop_requested():
    if STOP_REQUESTED:
        return True
    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
        except OSError:
            pass
        return True
    return False


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"started_at": datetime.datetime.now().isoformat(), "runs": []}


def save_state(state):
    os.makedirs(LOG_DIR, exist_ok=True)
    state["last_updated"] = datetime.datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def topic_iterator(topics):
    """Rotate through the topics, reshuffled each full pass, so runs vary."""
    while True:
        order = list(topics)
        random.shuffle(order)
        for topic in order:
            yield topic


def main():
    parser = argparse.ArgumentParser(description="Continuous Shorts maker (started by shortsctl start)")
    parser.add_argument("--context", required=True, help="Path to context.json")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    with open(args.context, encoding="utf-8") as f:
        config = json.load(f)

    topics = [t.strip() for t in config.get("topics", []) if t and t.strip()]
    gap = max(0, int(config.get("gap_minutes", 5))) * 60
    max_per_day = int(config.get("max_per_day", 0)) or None
    if not topics:
        logger.error("context.json has no topics; nothing to make.")
        return

    state = load_state()
    state["started_at"] = state.get("started_at") or datetime.datetime.now().isoformat()
    save_state(state)

    logger.info("Maker started: %d topic(s), gap %d min, uploads %s%s.",
                len(topics), gap // 60, args.privacy,
                f", max {max_per_day}/day" if max_per_day else "")
    schedule_gap_min = int(config.get("schedule_public_gap_minutes", config.get("gap_minutes", 5)))
    next_topics = topic_iterator(topics)

    while not stop_requested():
        today = datetime.date.today().isoformat()
        today_made = sum(1 for r in state["runs"]
                         if r.get("status") == "SUCCESS" and r.get("at", "").startswith(today))
        if max_per_day and today_made >= max_per_day:
            logger.info("Daily cap %d reached. Sleeping 30 minutes.", max_per_day)
            time.sleep(1800)
            continue

        topic = next(next_topics)
        logger.info("Making a Short on '%s' (%d made before this one)...", topic, len(state["runs"]))

        publish_at = None
        if schedule_gap_min > 0:
            publish_at = (datetime.datetime.now(datetime.timezone.utc) +
                          datetime.timedelta(minutes=schedule_gap_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info("Scheduled publish: private until %s (%d min gap), then public", publish_at, schedule_gap_min)

        mode = (config.get("mode") or "clip").strip().lower()
        if mode == "story":
            from scripts.story_pipeline import run_story
            result = run_story(topic, duration=int(config.get("duration", 45)),
                               privacy=args.privacy,
                               logo=os.getenv("LOGO_FILE") or None,
                               publish_at=publish_at)
        else:
            result = run(topic, privacy=args.privacy, style=config.get("editing_style") or None,
                         publish_at=publish_at)
        state["runs"].append({
            "at": datetime.datetime.now().isoformat(),
            "topic": topic,
            "status": result.get("status"),
            "youtube_url": result.get("youtube_url", ""),
            "publish_at": publish_at,
            "instagram_url": result.get("instagram_url", ""),
            "error": result.get("error") or result.get("failed_step", ""),
        })
        state["runs"] = state["runs"][-200:]
        save_state(state)

        if result.get("status") == "SUCCESS":
            logger.info("Uploaded %s -> %s (instagram: %s)", topic, result.get("youtube_url"),
                        result.get("instagram") or "not posted")
        else:
            logger.warning("Run failed at %s: %s", result.get("failed_step"), result.get("error"))

        if stop_requested():
            break
        for _ in range(gap):
            if stop_requested():
                break
            time.sleep(1)

    logger.info("Maker stopped. Total Shorts made this session: %d.",
                sum(1 for r in state["runs"] if r.get("status") == "SUCCESS"))


if __name__ == "__main__":
    main()
