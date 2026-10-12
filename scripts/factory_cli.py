#!/usr/bin/env python3
"""
Factory CLI - AI Shorts Factory
JSON-in / JSON-out adapter for the AgentTown connector.

Supported commands:
    python scripts/factory_cli.py find     --json '{"topic":"ocean waves"}'
    python scripts/factory_cli.py produce  --json '{"topic":"ocean waves","duration":30,"style":"cinematic","mode":"clip"}'
    python scripts/factory_cli.py publish  --json '{"file":"edited/x.mp4","platform":"youtube","privacy":"private","metadata":{...}}'
    python scripts/factory_cli.py maker    --json '{"action":"status"}'

Progress protocol:
    One JSON line per event to stdout:
    {"event":"step","step":"edit","status":"running","detail":"cinematic, 30s"}
    {"event":"step","step":"edit","status":"done"}
    {"event":"result","status":"SUCCESS", ...}

Exit codes:
    0 on success, 1 on failure (result line is always printed).
"""

import os
import sys
import json
import argparse
import datetime
import subprocess
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    stream=sys.stderr,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.content_finder import find_videos, rank_and_select_video, mock_mode
from scripts.run_pipeline import produce, publish_youtube_video, publish_instagram_video
import scripts.shortsctl as shortsctl


def emit_step(step: str, status: str, detail: str = None):
    payload = {"event": "step", "step": step, "status": status}
    if detail:
        payload["detail"] = str(detail)
    print(json.dumps(payload), flush=True)


def emit_result(result: dict) -> int:
    payload = {"event": "result", **result}
    print(json.dumps(payload), flush=True)
    return 0 if result.get("status") == "SUCCESS" else 1


def parse_payload(args) -> dict:
    data = {}
    if getattr(args, "json", None):
        try:
            data = json.loads(args.json)
        except Exception as e:
            emit_result({"status": "FAILED", "error": f"Invalid JSON payload: {e}"})
            sys.exit(1)
    return data


def handle_find(args) -> int:
    payload = parse_payload(args)
    topic = payload.get("topic") or getattr(args, "topic", None) or "nature"

    emit_step("find", "running", topic)
    try:
        videos = find_videos(topic)
        candidate = rank_and_select_video(videos)
        if not candidate:
            emit_step("find", "failed", f"No usable video found for '{topic}'")
            return emit_result({"status": "FAILED", "failed_step": "find",
                                "error": f"No usable video found for '{topic}'"})
        emit_step("find", "done")
        return emit_result({
            "status": "SUCCESS",
            "topic": topic,
            "candidate": candidate,
            "total_found": len(videos),
            "video_url": candidate.get("video_url"),
        })
    except Exception as e:
        emit_step("find", "failed", str(e))
        return emit_result({"status": "FAILED", "failed_step": "find", "error": str(e)})


def handle_produce(args) -> int:
    payload = parse_payload(args)
    topic = payload.get("topic") or getattr(args, "topic", None) or "ocean waves"
    duration = int(payload.get("duration") or getattr(args, "duration", None) or 30)
    style = payload.get("style") or getattr(args, "style", None) or "cinematic"
    mode = payload.get("mode") or getattr(args, "mode", None) or "clip"
    logo = payload.get("logo") or getattr(args, "logo", None) or os.getenv("LOGO_FILE")

    result = produce(
        topic=topic,
        duration=duration,
        style=style,
        logo=logo,
        mode=mode,
        on_progress=emit_step,
    )
    return emit_result(result)


def handle_publish(args) -> int:
    payload = parse_payload(args)
    file_path = payload.get("file") or getattr(args, "file", None)
    platform = (payload.get("platform") or getattr(args, "platform", None) or "youtube").lower()
    privacy = payload.get("privacy") or getattr(args, "privacy", None) or "private"
    meta = payload.get("metadata") or {}

    if not file_path or not os.path.exists(file_path):
        return emit_result({
            "status": "FAILED",
            "failed_step": "publish",
            "error": f"File not found: {file_path}",
        })

    title = meta.get("title") or payload.get("title") or "AI Short"
    description = meta.get("description") or payload.get("description") or ""
    tags = meta.get("tags") or payload.get("tags") or []
    caption = payload.get("caption")

    yt_res = None
    ig_res = None

    if platform in ("youtube", "both"):
        yt_res = publish_youtube_video(
            file_path,
            title=title,
            description=description,
            tags=tags,
            privacy=privacy,
            on_progress=emit_step,
        )
        if yt_res.get("status") != "SUCCESS":
            return emit_result({
                "status": "FAILED",
                "failed_step": "upload",
                "platform": "youtube",
                "error": yt_res.get("error", "YouTube upload failed"),
            })

    if platform in ("instagram", "both"):
        ig_res = publish_instagram_video(
            file_path,
            caption=caption,
            title=title,
            description=description,
            tags=tags,
            on_progress=emit_step,
        )
        if platform == "instagram" and ig_res.get("status") != "SUCCESS":
            return emit_result({
                "status": "FAILED",
                "failed_step": "upload_instagram",
                "platform": "instagram",
                "error": ig_res.get("error", "Instagram upload failed"),
            })

    res = {
        "status": "SUCCESS",
        "file": file_path,
        "platform": platform,
        "privacy": privacy,
    }
    if yt_res:
        res["youtube_url"] = yt_res.get("youtube_url")
        res["video_id"] = yt_res.get("video_id")
    if ig_res:
        res["instagram_url"] = ig_res.get("instagram_url", "")
        res["instagram_status"] = ig_res.get("status")

    return emit_result(res)


def handle_maker(args) -> int:
    payload = parse_payload(args)
    action = payload.get("action") or getattr(args, "action", None) or "status"

    if action == "status":
        state = shortsctl.load_state()
        runs = state.get("runs", [])
        made = sum(1 for r in runs if r.get("status") == "SUCCESS")
        today = datetime.date.today().isoformat()
        today_made = sum(1 for r in runs if r.get("status") == "SUCCESS" and r.get("at", "").startswith(today))
        running = shortsctl.daemon_running()

        return emit_result({
            "status": "SUCCESS",
            "action": "status",
            "running": running,
            "total_made": made,
            "today_made": today_made,
            "started_at": state.get("started_at"),
            "recent_runs": runs[-3:],
        })

    elif action == "start":
        if shortsctl.daemon_running():
            return emit_result({"status": "FAILED", "action": "start", "error": "Maker is already running"})

        context_file = payload.get("context") or shortsctl.CONTEXT_FILE
        privacy = payload.get("privacy") or "private"

        if not os.path.exists(context_file):
            return emit_result({"status": "FAILED", "action": "start",
                                "error": f"Context file not found at {context_file}"})

        if os.path.exists(shortsctl.STOP_FILE):
            try:
                os.remove(shortsctl.STOP_FILE)
            except OSError:
                pass

        os.makedirs(shortsctl.LOG_DIR, exist_ok=True)
        venv_py = os.path.join(ROOT, ".venv", "bin", "python")
        py_bin = venv_py if os.path.exists(venv_py) else sys.executable
        log_fd = os.open(shortsctl.DAEMON_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        proc = subprocess.Popen(
            [py_bin, os.path.join(ROOT, "scripts", "auto_run.py"),
             "--context", os.path.abspath(context_file), "--privacy", privacy],
            stdin=subprocess.DEVNULL,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            cwd=ROOT,
        )
        os.close(log_fd)
        shortsctl.write_json(shortsctl.PID_FILE, {"pid": proc.pid, "started_at": datetime.datetime.now().isoformat()})
        return emit_result({
            "status": "SUCCESS",
            "action": "start",
            "running": True,
            "pid": proc.pid,
            "privacy": privacy,
        })

    elif action == "stop":
        os.makedirs(shortsctl.LOG_DIR, exist_ok=True)
        open(shortsctl.STOP_FILE, "w").close()
        running = shortsctl.daemon_running()
        return emit_result({
            "status": "SUCCESS",
            "action": "stop",
            "running": False,
            "message": "Stop requested. Maker will finish current Short and stop.",
        })

    else:
        return emit_result({"status": "FAILED", "error": f"Unknown maker action: {action}"})


def main():
    parser = argparse.ArgumentParser(description="AI Shorts Factory Connector CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # find
    p_find = subparsers.add_parser("find", help="Find candidate stock video")
    p_find.add_argument("--json", type=str, help="JSON payload: {\"topic\": \"...\"}")
    p_find.add_argument("--topic", type=str, help="Search topic")
    p_find.set_defaults(func=handle_find)

    # produce
    p_produce = subparsers.add_parser("produce", help="Produce short without uploading")
    p_produce.add_argument("--json", type=str, help="JSON payload")
    p_produce.add_argument("--topic", type=str)
    p_produce.add_argument("--duration", type=int)
    p_produce.add_argument("--style", choices=["cinematic", "brainrot"])
    p_produce.add_argument("--mode", choices=["clip", "story"])
    p_produce.set_defaults(func=handle_produce)

    # publish
    p_publish = subparsers.add_parser("publish", help="Publish a produced short")
    p_publish.add_argument("--json", type=str, help="JSON payload")
    p_publish.add_argument("--file", type=str)
    p_publish.add_argument("--platform", choices=["youtube", "instagram", "both"])
    p_publish.add_argument("--privacy", choices=["private", "unlisted", "public"])
    p_publish.set_defaults(func=handle_publish)

    # maker
    p_maker = subparsers.add_parser("maker", help="Control continuous maker")
    p_maker.add_argument("action", nargs="?", choices=["status", "start", "stop"], default="status")
    p_maker.add_argument("--json", type=str, help="JSON payload: {\"action\": \"status|start|stop\"}")
    p_maker.set_defaults(func=handle_maker)

    args = parser.parse_args()
    code = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
