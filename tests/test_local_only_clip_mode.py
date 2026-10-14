"""Local-only safety: auto_run clip mode must honor upload=False / local_only=true.

Before this fix, scripts/auto_run.py computed upload_enabled but only passed it
to the story pipeline; the clip path called run_pipeline.run() with no upload
flag, and run() unconditionally called both publishers. A context.json with
upload=false or local_only=true therefore still produced live uploads in clip
mode. These tests prove the fix and pin the unchanged default behavior.
"""
import json
import os

import pytest

from scripts import auto_run
from scripts.run_pipeline import run


@pytest.fixture(autouse=True)
def _fresh_auto_state():
    """Isolate each auto_run test from session leftovers (STOP file, state)."""
    for path in (auto_run.STOP_FILE, auto_run.STATE_FILE):
        if os.path.exists(path):
            os.remove(path)
    yield
    if os.path.exists(auto_run.STOP_FILE):
        os.remove(auto_run.STOP_FILE)


def _install_recorders(monkeypatch):
    calls = {"yt": [], "ig": []}

    def fake_yt(*args, **kwargs):
        calls["yt"].append(kwargs)
        return {"status": "SUCCESS", "video_id": "mock_video_id",
                "youtube_url": "https://youtu.be/mock", "mode": "MOCK"}

    def fake_ig(*args, **kwargs):
        calls["ig"].append(kwargs)
        return {"status": "SUCCESS", "instagram_url": "https://instagram.com/mock"}

    monkeypatch.setattr("scripts.run_pipeline.publish_youtube_video", fake_yt)
    monkeypatch.setattr("scripts.run_pipeline.publish_instagram_video", fake_ig)
    return calls


def test_local_only_clip_mode_never_publishes(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    calls = _install_recorders(monkeypatch)
    result = run("ocean", duration=5, upload=False, keep_files=True)
    assert result["status"] == "SUCCESS", result
    assert result["mode"] == "LOCAL"
    assert result["youtube_url"] == ""
    assert result["instagram_url"] == ""
    assert calls["yt"] == [] and calls["ig"] == []
    assert os.path.exists(result["deliverable_file"])


def test_local_only_cleans_temp_but_keeps_deliverable(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    calls = _install_recorders(monkeypatch)
    result = run("ocean", duration=5, upload=False)
    assert result["status"] == "SUCCESS" and result["mode"] == "LOCAL"
    assert "cleanup" in result["steps"]
    assert os.path.exists(result["deliverable_file"])
    assert calls["yt"] == [] and calls["ig"] == []


def test_default_upload_behavior_unchanged(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    calls = _install_recorders(monkeypatch)
    # Keep the mock topic/asset out of the shared used-state so later tests
    # (test_pipeline_integration) still see a fresh candidate.
    monkeypatch.setattr("scripts.run_pipeline.mark_topic_used", lambda *a, **k: None)
    monkeypatch.setattr("scripts.run_pipeline.mark_asset_used", lambda *a, **k: None)
    result = run("ocean", duration=5, keep_files=True)
    assert result["status"] == "SUCCESS", result
    assert len(calls["yt"]) == 1 and len(calls["ig"]) == 1


def _run_auto_once(monkeypatch, tmp_path, config):
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(config), encoding="utf-8")
    seen = []

    def fake_run(topic, **kwargs):
        seen.append({"topic": topic, "kwargs": kwargs})
        with open(auto_run.STOP_FILE, "w", encoding="utf-8") as f:
            f.write("stop")
        local = kwargs.get("upload", True) is False
        return {"status": "SUCCESS", "mode": "LOCAL" if local else "MOCK",
                "topic": topic, "youtube_url": "", "deliverable_file": "d.mp4"}

    monkeypatch.setattr(auto_run, "run", fake_run)
    monkeypatch.setattr(auto_run.time, "sleep", lambda s: None)
    monkeypatch.setattr("sys.argv", ["auto_run.py", "--context", str(context_path)])
    auto_run.main()
    with open(auto_run.STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)
    return seen, state


def test_auto_run_clip_mode_passes_upload_false(monkeypatch, tmp_path):
    config = {"topics": ["t1"], "mode": "clip", "upload": False, "gap_minutes": 0}
    seen, state = _run_auto_once(monkeypatch, tmp_path, config)
    assert len(seen) == 1, seen
    assert seen[0]["kwargs"].get("upload") is False
    assert state["runs"][0]["status"] == "SUCCESS"
    assert state["runs"][0]["mode"] == "LOCAL"


def test_auto_run_clip_mode_default_uploads(monkeypatch, tmp_path):
    config = {"topics": ["t1"], "mode": "clip", "gap_minutes": 0}
    seen, state = _run_auto_once(monkeypatch, tmp_path, config)
    assert len(seen) == 1, seen
    assert seen[0]["kwargs"].get("upload") is True
    assert state["runs"][0]["status"] == "SUCCESS"
    assert state["runs"][0]["mode"] == "MOCK"
