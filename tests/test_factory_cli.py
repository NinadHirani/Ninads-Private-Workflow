import os
import sys
import json
import subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args):
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "factory_cli.py"), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip().startswith("{")]
    return proc.returncode, lines


def test_factory_cli_find_mock():
    code, events = run_cli("find", "--json", json.dumps({"topic": "ocean waves"}))
    assert code == 0
    steps = [e for e in events if e.get("event") == "step"]
    results = [e for e in events if e.get("event") == "result"]
    assert len(steps) >= 2
    assert steps[0]["step"] == "find"
    assert steps[0]["status"] == "running"
    assert steps[1]["status"] == "done"
    assert len(results) == 1
    assert results[0]["status"] == "SUCCESS"
    assert results[0]["topic"] == "ocean waves"


def test_factory_cli_produce_mock(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    code, events = run_cli("produce", "--json", json.dumps({
        "topic": "ocean waves",
        "duration": 5,
        "style": "cinematic",
        "mode": "clip"
    }))
    assert code == 0
    results = [e for e in events if e.get("event") == "result"]
    assert len(results) == 1
    res = results[0]
    assert res["status"] == "SUCCESS"
    assert os.path.exists(res["edited_path"])
    assert res["steps"]["validate_edited"]["width"] == 1080
    assert res["steps"]["validate_edited"]["height"] == 1920


def test_factory_cli_publish_mock(sample_video):
    code, events = run_cli("publish", "--json", json.dumps({
        "file": sample_video,
        "platform": "youtube",
        "privacy": "private",
        "metadata": {
            "title": "Test Title",
            "description": "Test Description",
            "tags": ["test"]
        }
    }))
    assert code == 0
    results = [e for e in events if e.get("event") == "result"]
    assert len(results) == 1
    res = results[0]
    assert res["status"] == "SUCCESS"
    assert "youtube_url" in res
    assert res["platform"] == "youtube"


def test_factory_cli_maker_status():
    code, events = run_cli("maker", "--json", json.dumps({"action": "status"}))
    assert code == 0
    results = [e for e in events if e.get("event") == "result"]
    assert len(results) == 1
    assert results[0]["status"] == "SUCCESS"
    assert "running" in results[0]
