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
try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text

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
    # Atomic write: a crash mid-write must never corrupt auto_state.json.
    # load_state() falls back to a fresh state on a corrupt file, which would
    # silently reset run history, the topic-dedup input and the daily-cap count.
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _sleep_with_stop(total_seconds, check_stop):
    """Sleep in 1-second ticks so the STOP file is honored within a second
    (e.g. during the 30-minute daily-cap nap). Returns True when stop was
    requested during the wait."""
    for _ in range(max(0, int(total_seconds))):
        if check_stop():
            return True
        time.sleep(1)
    return False


from scripts.logger import is_topic_used, mark_topic_used, get_used_topics

PROCEDURAL_ANGLES = [
    "mysteries of", "untold secrets of", "breathtaking views of", "hidden beauty of",
    "deep silence of", "rare sights of", "pure nature of",
    "cinematic journey through", "fascinating phenomena of", "calming sounds of"
]

def _gemini_url_and_headers(key: str):
    """Gemini endpoint with the API key in a header, never in the URL: request URLs
    end up in logs and error reports far more easily than headers do."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    return url, {"Content-Type": "application/json", "x-goog-api-key": key}


def generate_ai_topics(niche_context: str, count: int = 10) -> list:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return []
    import urllib.request
    used = list(get_used_topics())[-30:]
    prompt = f"""You are a viral YouTube Shorts producer.
Channel Niche/Context: {niche_context}
Generate {count} unique, high-retention, specific YouTube Short topics.
Avoid repeating or closely matching any of these existing topics: {used}
Output ONLY a raw JSON array of strings, for example: ["topic 1", "topic 2"]."""
    try:
        url, headers = _gemini_url_and_headers(key)
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            out = json.loads(resp.read().decode())
        text = out["candidates"][0]["content"]["parts"][0]["text"].strip()
        import re
        text = re.sub(r"^```(?:json)?\s*|```\s*$", "", text.strip(), flags=re.M).strip()
        items = json.loads(text)
        if isinstance(items, list):
            return [str(x).strip() for x in items if str(x).strip()]
    except Exception as e:
        logger.warning("Could not generate AI topics with Gemini: %s", redact(str(e)))
    return []

def generate_procedural_topics(base_topics: list) -> list:
    generated = []
    for base in base_topics:
        for angle in PROCEDURAL_ANGLES:
            generated.append(f"{angle} {base}")
            generated.append(f"{base} at twilight")
            generated.append(f"{base} early morning")
    random.shuffle(generated)
    return generated

def topic_iterator(topics, niche_context: str = ""):
    """Yields strictly fresh topics that have never been produced, expanding dynamically when needed."""
    pool = list(topics)
    while True:
        unused = [t for t in pool if not is_topic_used(t)]
        if not unused:
            logger.info("All current topics have been produced! Dynamically expanding with fresh unique topics...")
            new_topics = generate_ai_topics(niche_context or "viral shorts")
            if not new_topics:
                new_topics = generate_procedural_topics(topics)
            brand_new = [t for t in new_topics if not is_topic_used(t)]
            if not brand_new:
                # Timestamped variation fallback to strictly guarantee uniqueness
                brand_new = [f"{t} edition {int(time.time())}" for t in topics]
            pool.extend(brand_new)
            unused = brand_new

        next_topic = unused[0]
        pool.remove(next_topic)
        yield next_topic


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
    upload_enabled = bool(config.get("upload", True) and not config.get("local_only", False))
    if not topics:
        logger.error("context.json has no topics; nothing to make.")
        return

    state = load_state()
    state["started_at"] = state.get("started_at") or datetime.datetime.now().isoformat()
    save_state(state)

    logger.info("Maker started: %d topic(s), gap %d min, uploads %s%s (local deliverables active).",
                len(topics), gap // 60,
                args.privacy if upload_enabled else "OFF (local only)",
                f", max {max_per_day}/day" if max_per_day else "")
    schedule_gap_min = int(config.get("schedule_public_gap_minutes", config.get("gap_minutes", 5)))
    next_topics = topic_iterator(topics, niche_context=config.get("context", ""))

    while not stop_requested():
        today = datetime.date.today().isoformat()
        today_made = sum(1 for r in state["runs"]
                         if r.get("status") in ("SUCCESS", "SUCCESS_LOCAL") and r.get("at", "").startswith(today))
        if max_per_day and today_made >= max_per_day:
            logger.info("Daily cap %d reached. Sleeping 30 minutes.", max_per_day)
            if _sleep_with_stop(1800, stop_requested):
                break
            continue

        topic = next(next_topics)
        logger.info("Making a Short on '%s' (%d made before this one)...", topic, len(state["runs"]))

        publish_at = None
        if upload_enabled and schedule_gap_min > 0:
            publish_at = (datetime.datetime.now(datetime.timezone.utc) +
                          datetime.timedelta(minutes=schedule_gap_min)).strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info("Scheduled publish: private until %s (%d min gap), then public", publish_at, schedule_gap_min)

        mode = (config.get("mode") or "clip").strip().lower()
        if mode == "story":
            from scripts.story_pipeline import run_story
            result = run_story(topic, duration=int(config.get("duration", 45)),
                               privacy=args.privacy,
                               logo=os.getenv("LOGO_FILE") or None,
                               publish_at=publish_at,
                               upload=upload_enabled)
        else:
            result = run(topic, privacy=args.privacy, style=config.get("editing_style") or None,
                         publish_at=publish_at, upload=upload_enabled)

        is_success = result.get("status") in ("SUCCESS", "SUCCESS_LOCAL")
        deliverable = result.get("deliverable_file", "")
        state["runs"].append({
            "at": datetime.datetime.now().isoformat(),
            "topic": topic,
            "status": "SUCCESS" if is_success else "FAILED",
            "mode": result.get("mode", ""),
            "youtube_url": result.get("youtube_url", ""),
            "deliverable": deliverable,
            "publish_at": publish_at,
            "instagram_url": result.get("instagram_url", ""),
            "error": result.get("queue_reason") or result.get("error") or result.get("failed_step", ""),
        })
        state["runs"] = state["runs"][-200:]
        save_state(state)

        if is_success:
            if result.get("youtube_url"):
                logger.info("Uploaded %s -> %s (saved: %s)", topic, result.get("youtube_url"), deliverable)
            elif result.get("queue_reason"):
                logger.info("Created Short on '%s' -> %s (%s)", topic, deliverable, result.get("queue_reason"))
            else:
                logger.info("Created Short on '%s' -> %s", topic, deliverable)
        else:
            logger.warning("Run failed at %s: %s", result.get("failed_step"), result.get("error"))

        if stop_requested():
            break
        if _sleep_with_stop(gap, stop_requested):
            break

    logger.info("Maker stopped. Total Shorts made this session: %d.",
                sum(1 for r in state["runs"] if r.get("status") in ("SUCCESS", "SUCCESS_LOCAL")))


if __name__ == "__main__":
    main()
