#!/usr/bin/env python3
"""
Shorts Control - AI Shorts Factory
One-click control for the continuous Shorts maker:

    python scripts/shortsctl.py connect          # connect YouTube and Instagram once
    python scripts/shortsctl.py start            # start making + uploading Shorts
    python scripts/shortsctl.py stop             # stop the maker immediately
    python scripts/shortsctl.py status           # check status and recent uploads

The maker reads context.json (what kind of videos you want) and keeps producing
until you run stop.
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


def get_daemon_pid():
    raw = read_json(PID_FILE, {}).get("pid")
    try:
        return int(raw) if raw is not None else None
    except (ValueError, TypeError):
        return None


def daemon_running():
    pid = get_daemon_pid()
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        # Process does not exist (stale PID file) - clean it up
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except OSError:
                pass
        return False


def stop_process(pid, timeout=4.0):
    """Terminate the daemon process and its process group cleanly."""
    try:
        my_pgid = os.getpgrp()
    except OSError:
        my_pgid = None

    try:
        pgid = os.getpgid(pid)
        if pgid == my_pgid:
            pgid = None
    except OSError:
        pgid = None

    def _send_signal(sig):
        try:
            if pgid is not None:
                os.killpg(pgid, sig)
            else:
                os.kill(pid, sig)
        except OSError:
            pass

    _send_signal(signal.SIGTERM)
    start_t = time.time()
    while time.time() - start_t < timeout:
        try:
            os.kill(pid, 0)
            time.sleep(0.2)
        except OSError:
            return True

    # If still alive after timeout, force kill
    _send_signal(signal.SIGKILL)
    time.sleep(0.3)
    try:
        os.kill(pid, 0)
        return False
    except OSError:
        return True


def load_state():
    return read_json(STATE_FILE, {"started_at": None, "runs": []})


def cmd_connect(args):
    sys.path.insert(0, ROOT)
    results = {}
    if args.platform in ("youtube", "both"):
        from scripts.connect_youtube import connect
        results["youtube"] = connect()
    if args.platform in ("instagram", "both"):
        from scripts.instagram_uploader import connect_instagram
        results["instagram"] = connect_instagram()
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(r.get("status") == "SUCCESS" for r in results.values()) else 1)


def cmd_start(args):
    if not os.path.exists(args.context):
        print(f"No context file at {args.context}. Create one, e.g.:")
        print(json.dumps({"context": "calming nature shorts with soft music",
                          "topics": ["ocean waves", "waterfall", "sunset timelapse"],
                          "gap_minutes": 5}, indent=2))
        sys.exit(1)

    if daemon_running():
        pid = get_daemon_pid()
        print(f"The maker is already running (PID {pid}). Use `status` to inspect or `stop` to stop it.")
        sys.exit(1)

    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
        except OSError:
            pass

    os.makedirs(LOG_DIR, exist_ok=True)
    venv_py = os.path.join(ROOT, ".venv", "bin", "python")
    py_bin = venv_py if os.path.exists(venv_py) else sys.executable
    log_fd = os.open(DAEMON_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    proc = subprocess.Popen(
        [py_bin, os.path.join(ROOT, "scripts", "auto_run.py"),
         "--context", os.path.abspath(args.context), "--privacy", args.privacy],
        stdin=subprocess.DEVNULL,
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
        cwd=ROOT,
    )
    os.close(log_fd)
    write_json(PID_FILE, {"pid": proc.pid, "started_at": datetime.datetime.now().isoformat()})
    print(f"Started maker (PID {proc.pid}). Uploading {args.privacy} from '{os.path.basename(args.context)}'. "
          f"Run `status` any time, `stop` to stop.")


def cmd_stop(args):
    pid = get_daemon_pid()
    running = daemon_running()

    if running and pid:
        print(f"Stopping maker (PID {pid})...")
        stop_process(pid)
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except OSError:
                pass
        if os.path.exists(STOP_FILE):
            try:
                os.remove(STOP_FILE)
            except OSError:
                pass
        state = load_state()
        done = sum(1 for r in state.get("runs", []) if r.get("status") == "SUCCESS")
        print(f"Maker stopped. Total Shorts made so far: {done}.")
    else:
        # Clean up any leftover stale files
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except OSError:
                pass
        if os.path.exists(STOP_FILE):
            try:
                os.remove(STOP_FILE)
            except OSError:
                pass
        print("The maker is not running. Nothing to stop.")


def cmd_status(args):
    state = load_state()
    runs = state.get("runs", [])
    made = sum(1 for r in runs if r.get("status") in ("SUCCESS", "SUCCESS_LOCAL"))
    today = datetime.date.today().isoformat()
    today_made = sum(1 for r in runs if r.get("status") in ("SUCCESS", "SUCCESS_LOCAL") and r.get("at", "").startswith(today))
    running = daemon_running()
    pid = get_daemon_pid() if running else None

    status_str = f"RUNNING (PID {pid})" if running else "stopped"
    print(f"Maker: {status_str}")
    print(f"Shorts made: {made} total, {today_made} today")
    if state.get("started_at"):
        print(f"Started: {state['started_at']}")
    if runs:
        print("\nRecent runs:")
        for r in runs[-5:]:
            line = f"  {r.get('at', '')[:16]}  {r.get('topic', '')}  [{r.get('status', 'UNKNOWN')}]"
            if r.get("youtube_url"):
                line += f"  {r['youtube_url']}"
            elif r.get("deliverable"):
                line += f"  (saved: {os.path.basename(r['deliverable'])})"
            if r.get("instagram_url"):
                line += f"  {r['instagram_url']}"
            if r.get("status") != "SUCCESS" and r.get("error"):
                line += f"  ({r['error'][:50]})"
            print(line)


def cmd_ui(args):
    import scripts.web_ui as web_ui
    web_ui.run_server(port=args.port, host=args.host)


PLIST_LABEL = "com.shortsfactory.webui"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")


def cmd_service(args):
    action = args.action
    python_bin = os.path.join(ROOT, ".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable

    web_ui_script = os.path.join(ROOT, "scripts", "web_ui.py")
    log_file = os.path.join(LOG_DIR, "web_ui.log")

    if action == "install":
        os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{web_ui_script}</string>
        <string>--port</string>
        <string>{args.port}</string>
        <string>--host</string>
        <string>0.0.0.0</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_file}</string>
    <key>StandardErrorPath</key>
    <string>{log_file}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:{ROOT}/.venv/bin</string>
    </dict>
</dict>
</plist>
"""
        with open(PLIST_PATH, "w", encoding="utf-8") as f:
            f.write(plist_content)

        subprocess.run(["launchctl", "unload", PLIST_PATH], stderr=subprocess.DEVNULL)
        res = subprocess.run(["launchctl", "load", "-w", PLIST_PATH], capture_output=True, text=True)
        if res.returncode == 0:
            print("Service successfully deployed & installed as LaunchAgent!")
            print(f"Service Label: {PLIST_LABEL}")
            print(f"Plist Path:    {PLIST_PATH}")
            print(f"Mobile UI:     http://localhost:{args.port} or http://<lan-ip>:{args.port}")
        else:
            print(f"Launchctl warning: {res.stderr.strip()}")

    elif action == "uninstall":
        if os.path.exists(PLIST_PATH):
            subprocess.run(["launchctl", "unload", PLIST_PATH], stderr=subprocess.DEVNULL)
            os.remove(PLIST_PATH)
            print("Service uninstalled and removed from LaunchAgents.")
        else:
            print("Service is not installed.")

    elif action == "restart":
        if os.path.exists(PLIST_PATH):
            subprocess.run(["launchctl", "unload", PLIST_PATH], stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            subprocess.run(["launchctl", "load", "-w", PLIST_PATH])
            print("Service reloaded & restarted.")
        else:
            print("Service plist not found. Run 'python scripts/shortsctl.py service install' first.")

    elif action == "status":
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        found = [line for line in res.stdout.splitlines() if PLIST_LABEL in line]
        if found:
            print(f"Service '{PLIST_LABEL}' is ACTIVE (launchd):")
            print("  PID\tStatus\tLabel")
            print("  " + found[0])
        else:
            print(f"Service '{PLIST_LABEL}' is NOT loaded in launchd.")


def cmd_clean(args):
    from scripts.purge_and_index import run_purge_and_index
    run_purge_and_index(dry_run=args.dry_run)


def cmd_tunnel(args):
    port = args.port
    print("=" * 60)
    print("  🌐 SECURE HTTPS TUNNEL FOR VERCEL MOBILE APP")
    print(f"  Target: http://localhost:{port}")
    print("=" * 60)
    print("Starting secure tunnel... Copy the HTTPS URL into your Vercel Settings.")
    print("Press Ctrl+C to stop tunnel.")
    try:
        subprocess.run(["npx", "-y", "localtunnel", "--port", str(port)])
    except KeyboardInterrupt:
        print("\nTunnel closed.")


def main():
    parser = argparse.ArgumentParser(description="One-click control for AI Shorts Factory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_connect = sub.add_parser("connect", help="Connect your YouTube and Instagram accounts once")
    p_connect.add_argument("--platform", default="both", choices=["youtube", "instagram", "both"])
    p_start = sub.add_parser("start", help="Start making and uploading Shorts")
    p_start.add_argument("--context", default=CONTEXT_FILE, help=f"Path to context.json (default: {CONTEXT_FILE})")
    p_start.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    sub.add_parser("stop", help="Stop the maker immediately")
    sub.add_parser("status", help="Show what has been made and maker state")
    p_clean = sub.add_parser("clean", help="Index history into deduplication and purge media files")
    p_clean.add_argument("--dry-run", action="store_true", help="Preview files to be deleted without removing them")
    p_ui = sub.add_parser("ui", help="Start mobile web control center")
    p_ui.add_argument("--port", type=int, default=8088, help="Port to listen on (default: 8088)")
    p_ui.add_argument("--host", type=str, default="0.0.0.0", help="Host binding (default: 0.0.0.0)")

    p_service = sub.add_parser("service", help="Manage permanent background daemon service (launchd)")
    p_service.add_argument("action", choices=["install", "uninstall", "restart", "status"], help="Action to execute")
    p_service.add_argument("--port", type=int, default=8088, help="Port for the service (default: 8088)")

    p_tunnel = sub.add_parser("tunnel", help="Open a secure HTTPS tunnel to connect from Vercel")
    p_tunnel.add_argument("--port", type=int, default=8088, help="Port to tunnel (default: 8088)")

    args = parser.parse_args()
    handlers = {
        "connect": cmd_connect,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "clean": cmd_clean,
        "ui": cmd_ui,
        "service": cmd_service,
        "tunnel": cmd_tunnel,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
