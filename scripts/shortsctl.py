#!/usr/bin/env python3
"""
Shorts Control - AI Shorts Factory
One-click control for the continuous Shorts maker:

    python scripts/shortsctl.py connect          # connect your YouTube channel once
    python scripts/shortsctl.py start            # start making + uploading Shorts (private)
    python scripts/shortsctl.py stop             # stop after the current Short finishes
    python scripts/shortsctl.py status           # what the maker has done so far

The maker reads context.json (what kind of videos you want) and keeps producing
until you run stop. Every upload is private by default so you can review first.
"""

import os
import sys
import json
import time
import signal
import argparse
import subprocess
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, os.getenv("LOG_PATH", "logs"))
PID_FILE = os.path.join(LOG_DIR, "auto.pid")
STOP_FILE = os.path.join(LOG_DIR, "STOP")
STATE_FILE = os.path.join(LOG_DIR, "auto_state.json")
DAEMON_LOG = os.path.join(LOG_DIR, "auto.log")
CONTEXT_FILE = os.path.join(ROOT, "context.json")


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def daemon_running():
    pid = read_json(PID_FILE, {}).get("pid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def load_state():
    return read_json(STATE_FILE, {"started_at": None, "runs": []})


def cmd_connect(args):
    sys.path.insert(0, ROOT)
    from scripts.connect_youtube import connect
    result = connect()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") == "SUCCESS" else 1)


def cmd_start(args):
    if not os.path.exists(args.context):
        print(f"No context file at {args.context}. Create one, e.g.:")
        print(json.dumps({"context": "calming nature shorts with soft music",
                          "topics": ["ocean waves", "waterfall", "sunset timelapse"],
                          "gap_minutes": 5}, indent=2))
        sys.exit(1)
    if daemon_running():
        print("The maker is already running. Use `status` to see it, or `stop` to stop it.")
        sys.exit(1)
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(DAEMON_LOG, "ab") as log:
        proc = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "scripts", "auto_run.py"),
             "--context", os.path.abspath(args.context), "--privacy", args.privacy],
            stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=ROOT,
        )
    write_json(PID_FILE, {"pid": proc.pid, "started_at": datetime.datetime.now().isoformat()})
    print(f"Started. PID {proc.pid}. It makes Shorts from {os.path.basename(args.context)} "
          f"and uploads them {args.privacy}. Run `status` any time, `stop` to stop it.")


def cmd_stop(args):
    os.makedirs(LOG_DIR, exist_ok=True)
    open(STOP_FILE, "w").close()
    state = load_state()
    done = sum(1 for r in state.get("runs", []) if r.get("status") == "SUCCESS")
    if daemon_running():
        print(f"Stop requested. The current Short finishes first, then the maker stops. {done} Short(s) made so far.")
    else:
        print("The maker is not running. Nothing to stop.")


def cmd_status(args):
    state = load_state()
    runs = state.get("runs", [])
    made = sum(1 for r in runs if r.get("status") == "SUCCESS")
    today = datetime.date.today().isoformat()
    today_made = sum(1 for r in runs if r.get("status") == "SUCCESS" and r.get("at", "").startswith(today))
    running = daemon_running()
    print(f"Maker: {'RUNNING' if running else 'stopped'}")
    print(f"Shorts made: {made} total, {today_made} today")
    if state.get("started_at"):
        print(f"Started: {state['started_at']}")
    for r in runs[-3:]:
        line = f"  {r.get('at', '')[:16]}  {r.get('topic')}  {r.get('status')}"
        if r.get("youtube_url"):
            line += f"  {r['youtube_url']}"
        print(line)


def main():
    parser = argparse.ArgumentParser(description="One-click control for AI Shorts Factory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("connect", help="Connect your YouTube channel once (OAuth)")
    p_start = sub.add_parser("start", help="Start making and uploading Shorts")
    p_start.add_argument("--context", default=CONTEXT_FILE, help=f"Path to context.json (default: {CONTEXT_FILE})")
    p_start.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    sub.add_parser("stop", help="Stop the maker after the current Short")
    sub.add_parser("status", help="Show what has been made")

    args = parser.parse_args()
    {"connect": cmd_connect, "start": cmd_start, "stop": cmd_stop, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    main()
