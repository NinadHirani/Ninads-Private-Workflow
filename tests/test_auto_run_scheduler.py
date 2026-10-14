"""auto_run reliability: STOP honored during the daily-cap nap; atomic state writes."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import auto_run  # noqa: E402


def test_save_state_atomic_writes_and_leaves_no_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(auto_run, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(auto_run, "STATE_FILE", str(tmp_path / "auto_state.json"))

    state = {"started_at": "2026-10-15T00:00:00", "runs": [{"topic": "t", "status": "SUCCESS"}]}
    auto_run.save_state(state)

    saved = tmp_path / "auto_state.json"
    assert saved.exists()
    assert json.loads(saved.read_text(encoding="utf-8"))["runs"][0]["topic"] == "t"
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], "a completed save must not leave a .tmp behind"


def test_cap_sleep_honors_stop_within_a_tick(monkeypatch):
    """During the 30-minute daily-cap nap, a STOP request must break out in
    seconds, not after the full 1800-second sleep."""
    sleeps = []
    monkeypatch.setattr(auto_run.time, "sleep", lambda s: sleeps.append(s))

    ticks = {"n": 0}

    def stop_after_three():
        ticks["n"] += 1
        return ticks["n"] > 3

    stopped = auto_run._sleep_with_stop(1800, stop_after_three)
    assert stopped is True
    assert sleeps == [1.0] * 3, "only 3 one-second ticks, not a 1800s block"


def test_sleep_completes_normally_without_stop(monkeypatch):
    sleeps = []
    monkeypatch.setattr(auto_run.time, "sleep", lambda s: sleeps.append(s))

    stopped = auto_run._sleep_with_stop(3, lambda: False)
    assert stopped is False
    assert sleeps == [1.0] * 3


def test_safe_run_survives_story_exception(monkeypatch):
    """An unexpected exception from run_story must become a FAILED result, so
    the continuous maker records the run and keeps going instead of dying."""
    import argparse

    import scripts.story_pipeline as story_pipeline

    def boom(*a, **k):
        raise RuntimeError("boom: unexpected failure")

    monkeypatch.setattr(story_pipeline, "run_story", boom)
    args = argparse.Namespace(privacy="private")
    result = auto_run._safe_run("story", "topic-under-test", args, {"duration": 45},
                                None, False)
    assert result["status"] == "FAILED"
    assert "RuntimeError" in result["error"] and "boom" in result["error"]


def test_safe_run_survives_clip_exception(monkeypatch):
    """Same containment for clip mode: run() raising must not kill the maker."""
    import argparse

    def boom(*a, **k):
        raise ValueError("clip pipeline exploded")

    monkeypatch.setattr(auto_run, "run", boom)
    args = argparse.Namespace(privacy="private")
    result = auto_run._safe_run("clip", "topic-under-test", args, {},
                                None, False)
    assert result["status"] == "FAILED"
    assert "ValueError" in result["error"]
