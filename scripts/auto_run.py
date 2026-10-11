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

STOP_REQUESTED = False


def _handle(sig, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True


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
        result = run(topic, privacy=args.privacy)
        state["runs"].append({
            "at": datetime.datetime.now().isoformat(),
            "topic": topic,
            "status": result.get("status"),
            "youtube_url": result.get("youtube_url", ""),
            "error": result.get("error") or result.get("failed_step", ""),
        })
        state["runs"] = state["runs"][-200:]
        save_state(state)

        if result.get("status") == "SUCCESS":
            logger.info("Uploaded %s -> %s", topic, result.get("youtube_url"))
        else:
            logger.warning("Run failed at %s: %s", result.get("failed_step"), result.get("error"))

        if stop_requested():
            break
        time.sleep(gap)

    logger.info("Maker stopped. Total Shorts made this session: %d.",
                sum(1 for r in state["runs"] if r.get("status") == "SUCCESS"))


if __name__ == "__main__":
    main()
