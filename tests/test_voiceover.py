"""Voiceover fallback reliability: edge-tts retries must not break the fallback chain."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import voiceover  # noqa: E402


def test_retry_then_success(monkeypatch):
    """First edge-tts attempt fails (e.g. 403), retry with the same voice succeeds."""
    calls = []
    sleeps = []

    def fake_edge(text, out_dir, wav, voice=None):
        calls.append(voice)
        if len(calls) < 2:
            raise RuntimeError("403 Forbidden")
        return [{"word": "hi", "start": 0.0, "end": 0.2}]

    monkeypatch.setattr(voiceover, "_edge", fake_edge)
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: sleeps.append(s))
    result = voiceover.make_voiceover(["hello world"], "/tmp/vo_test_retry")
    assert result["status"] == "SUCCESS"
    assert result["voice"].startswith("edge-tts:")
    assert len(calls) == 2
    assert sleeps, "a backoff sleep should happen between attempts"


def test_falls_back_to_piper(monkeypatch):
    """Every edge-tts attempt fails; the Piper fallback still produces a voiceover."""
    monkeypatch.setattr(voiceover, "_edge", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("403")))
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: None)
    monkeypatch.setattr(voiceover, "_piper_available", lambda: True)
    monkeypatch.setattr(voiceover, "_piper", lambda text, wav: [{"word": "hi", "start": 0.0, "end": 0.2}])
    result = voiceover.make_voiceover(["hello world"], "/tmp/vo_test_piper")
    assert result["status"] == "SUCCESS"
    assert result["voice"] == "piper"


def test_all_methods_fail(monkeypatch):
    """Every method failing must return a clean FAILED result, not raise."""
    monkeypatch.setattr(voiceover, "_edge", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: None)
    monkeypatch.setattr(voiceover, "_piper_available", lambda: False)
    monkeypatch.delenv("EDGE_TTS_ATTEMPTS", raising=False)
    result = voiceover.make_voiceover(["hello world"], "/tmp/vo_test_fail")
    assert result["status"] == "FAILED"
    assert "edge-tts" in result["error"]


def test_retry_attempts_env(monkeypatch):
    """EDGE_TTS_ATTEMPTS caps tries per voice."""
    calls = []
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "3")
    monkeypatch.setattr(voiceover, "_edge", lambda text, out_dir, wav, voice=None: calls.append(voice) or (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: None)
    monkeypatch.setattr(voiceover, "_piper_available", lambda: False)
    monkeypatch.setattr(voiceover, "VOICES_FALLBACK", ["v1"])
    result = voiceover.make_voiceover(["hello"], "/tmp/vo_test_env")
    assert result["status"] == "FAILED"
    assert calls == ["v1", "v1", "v1"]
