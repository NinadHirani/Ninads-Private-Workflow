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
