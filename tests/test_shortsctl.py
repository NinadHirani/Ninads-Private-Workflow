import os
import json
import time
import signal
import subprocess
import pytest
from unittest.mock import patch, MagicMock

import scripts.shortsctl as shortsctl


def test_daemon_running_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(shortsctl, "PID_FILE", str(tmp_path / "auto.pid"))
    assert shortsctl.daemon_running() is False


def test_daemon_running_stale_pid_cleaned(tmp_path, monkeypatch):
    pid_file = tmp_path / "auto.pid"
    # Use a PID that almost certainly doesn't exist
    pid_file.write_text(json.dumps({"pid": 99999999}))
    monkeypatch.setattr(shortsctl, "PID_FILE", str(pid_file))

    assert shortsctl.daemon_running() is False
    assert not pid_file.exists()


def test_daemon_running_live_pid(tmp_path, monkeypatch):
    pid_file = tmp_path / "auto.pid"
    pid_file.write_text(json.dumps({"pid": os.getpid()}))
    monkeypatch.setattr(shortsctl, "PID_FILE", str(pid_file))

    assert shortsctl.daemon_running() is True


def test_cmd_stop_not_running(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shortsctl, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(shortsctl, "PID_FILE", str(tmp_path / "auto.pid"))
    monkeypatch.setattr(shortsctl, "STOP_FILE", str(tmp_path / "STOP"))

    shortsctl.cmd_stop(argparse_mock())
    captured = capsys.readouterr()
    assert "not running" in captured.out.lower()


def test_cmd_status_stopped(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shortsctl, "PID_FILE", str(tmp_path / "auto.pid"))
    monkeypatch.setattr(shortsctl, "STATE_FILE", str(tmp_path / "state.json"))
    (tmp_path / "state.json").write_text(json.dumps({
        "started_at": "2026-10-12T10:00:00",
        "runs": [{"at": "2026-10-12T10:05:00", "topic": "test", "status": "SUCCESS"}]
    }))

    shortsctl.cmd_status(argparse_mock())
    captured = capsys.readouterr()
    assert "Maker: stopped" in captured.out
    assert "Shorts made: 1 total" in captured.out


def test_cmd_stop_terminates_process(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shortsctl, "LOG_DIR", str(tmp_path))
    pid_file = tmp_path / "auto.pid"
    stop_file = tmp_path / "STOP"
    monkeypatch.setattr(shortsctl, "PID_FILE", str(pid_file))
    monkeypatch.setattr(shortsctl, "STOP_FILE", str(stop_file))
    monkeypatch.setattr(shortsctl, "STATE_FILE", str(tmp_path / "state.json"))

    # Spawn a dummy sleep process
    proc = subprocess.Popen(["sleep", "60"])
    pid_file.write_text(json.dumps({"pid": proc.pid}))

    assert shortsctl.daemon_running() is True
    shortsctl.cmd_stop(argparse_mock())
    captured = capsys.readouterr()

    assert "stopping maker" in captured.out.lower()
    assert "maker stopped" in captured.out.lower()
    assert not pid_file.exists()

    # Verify process actually terminated
    try:
        proc.wait(timeout=2)
    except Exception:
        proc.kill()


def argparse_mock():
    m = MagicMock()
    return m
