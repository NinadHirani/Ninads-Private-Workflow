"""Voiceover fallback reliability: edge-tts retries must not break the fallback chain."""
import os
import subprocess
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


def test_invalid_env_values_do_not_break_fallback(monkeypatch):
    """Garbage EDGE_TTS_* values must fall back to defaults, not crash before the chain starts."""
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "not-a-number")
    monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", "-100")
    sleeps = []
    calls = []

    def fake_edge(text, out_dir, wav, voice=None):
        calls.append(voice)
        return [{"word": "hi", "start": 0.0, "end": 0.2}]

    monkeypatch.setattr(voiceover, "_edge", fake_edge)
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: sleeps.append(s))
    result = voiceover.make_voiceover(["hello"], "/tmp/vo_test_bad_env")
    assert result["status"] == "SUCCESS"
    assert len(calls) == 1, "defaults (2 attempts) mean the second attempt never runs after success"


def test_extreme_and_negative_env_values_are_clamped(monkeypatch):
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "999")
    assert voiceover._bounded_int_env("EDGE_TTS_ATTEMPTS", 2, 1, 10) == 10
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "0")
    assert voiceover._bounded_int_env("EDGE_TTS_ATTEMPTS", 2, 1, 10) == 1
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "-3")
    assert voiceover._bounded_int_env("EDGE_TTS_ATTEMPTS", 2, 1, 10) == 1
    monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", "abc")
    assert voiceover._bounded_float_env("EDGE_TTS_BACKOFF_SECONDS", 2.0, 0.0, 60.0) == 2.0
    monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", "1e9")
    assert voiceover._bounded_float_env("EDGE_TTS_BACKOFF_SECONDS", 2.0, 0.0, 60.0) == 60.0
    monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", "-5")
    assert voiceover._bounded_float_env("EDGE_TTS_BACKOFF_SECONDS", 2.0, 0.0, 60.0) == 0.0


def test_edge_intermediates_are_cleaned_up(monkeypatch, tmp_path):
    """vo.mp3 and vo.vtt are removed once the final wav exists; a cleanup failure never raises."""
    mp3 = tmp_path / "vo.mp3"
    vtt = tmp_path / "vo.vtt"
    wav = tmp_path / "voiceover.wav"
    mp3.write_bytes(b"mp3-bytes")
    vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n")

    class Ok:
        returncode = 0

    monkeypatch.setattr(voiceover.subprocess, "run", lambda *a, **k: Ok())
    words = voiceover._edge("hello", str(tmp_path), str(wav))
    assert words, "word timings still parsed from the vtt before cleanup"
    assert not mp3.exists() and not vtt.exists()


def test_non_finite_float_env_falls_back_to_default(monkeypatch):
    """NaN/Inf EDGE_TTS_BACKOFF_SECONDS must fall back to the default, not pass through."""
    for raw in ("nan", "NaN", "inf", "-inf", "infinity"):
        monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", raw)
        assert voiceover._bounded_float_env("EDGE_TTS_BACKOFF_SECONDS", 2.0, 0.0, 60.0) == 2.0


def test_nan_backoff_never_reaches_sleep(monkeypatch):
    """EDGE_TTS_BACKOFF_SECONDS=nan must never hand a NaN (or inf) delay to time.sleep."""
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "2")
    monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", "nan")
    sleeps = []
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(voiceover, "_edge", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(voiceover, "_piper_available", lambda: False)
    monkeypatch.setattr(voiceover, "VOICES_FALLBACK", ["v1"])
    result = voiceover.make_voiceover(["hello"], "/tmp/vo_test_nan")
    assert result["status"] == "FAILED"
    assert sleeps, "the retry path should still sleep between attempts"
    assert all(s == s and abs(s) != float("inf") for s in sleeps), "no non-finite delay may reach sleep"


def test_retry_delay_is_capped(monkeypatch):
    """Exponential backoff can never exceed MAX_RETRY_DELAY_SECONDS per wait."""
    monkeypatch.setenv("EDGE_TTS_ATTEMPTS", "10")
    monkeypatch.setenv("EDGE_TTS_BACKOFF_SECONDS", "60")
    sleeps = []
    monkeypatch.setattr(voiceover.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(voiceover, "_edge", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(voiceover, "_piper_available", lambda: False)
    monkeypatch.setattr(voiceover, "VOICES_FALLBACK", ["v1"])
    result = voiceover.make_voiceover(["hello"], "/tmp/vo_test_cap")
    assert result["status"] == "FAILED"
    assert len(sleeps) >= 9, "attempts 1..9 each wait before the next try"
    assert all(s <= voiceover.MAX_RETRY_DELAY_SECONDS for s in sleeps)
    assert max(sleeps) == voiceover.MAX_RETRY_DELAY_SECONDS, "the uncapped 60*2^8 wait is clamped to the cap"


def test_failed_edge_tts_cleans_up_partial_intermediates(monkeypatch, tmp_path):
    """A failing edge-tts subprocess must not leave partial vo.mp3/vo.vtt behind."""
    mp3 = tmp_path / "vo.mp3"
    vtt = tmp_path / "vo.vtt"
    mp3.write_bytes(b"partial-mp3")
    vtt.write_text("WEBVTT\n")

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, ["edge_tts"])

    monkeypatch.setattr(voiceover.subprocess, "run", boom)
    with pytest.raises(Exception):
        voiceover._edge("hello", str(tmp_path), str(tmp_path / "voiceover.wav"))
    assert not mp3.exists() and not vtt.exists()


def test_failed_ffmpeg_conversion_cleans_up_intermediates(monkeypatch, tmp_path):
    """vo.mp3/vo.vtt are removed even when the FFmpeg wav conversion itself fails."""
    mp3 = tmp_path / "vo.mp3"
    vtt = tmp_path / "vo.vtt"
    mp3.write_bytes(b"mp3-bytes")
    vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n")

    class Ok:
        returncode = 0

    def fake_run(cmd, **k):
        if str(cmd[0]).endswith("ffmpeg") or "ffmpeg" in str(cmd[0]):
            raise subprocess.CalledProcessError(1, cmd)
        return Ok()

    monkeypatch.setattr(voiceover.subprocess, "run", fake_run)
    with pytest.raises(Exception):
        voiceover._edge("hello", str(tmp_path), str(tmp_path / "voiceover.wav"))
    assert not mp3.exists() and not vtt.exists()


def test_failed_macos_say_cleans_up_partial_aiff(monkeypatch, tmp_path):
    """A failed say/FFmpeg conversion must not leave a partial vo.aiff behind."""
    aiff = tmp_path / "vo.aiff"
    aiff.write_bytes(b"partial-aiff")

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, ["say"])

    monkeypatch.setattr(voiceover.subprocess, "run", boom)
    with pytest.raises(Exception):
        voiceover._macos_say("hello", str(tmp_path), str(tmp_path / "voiceover.wav"))
    assert not aiff.exists()
