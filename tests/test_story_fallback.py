"""Regression tests for the story pipeline FFmpeg fallback.

Two defects were found during the Oct 14, 2026 engine comparison:
1. steps['edit']['engine'] recorded "remotion" even when the FFmpeg fallback
   produced the final video.
2. The fallback ignored image-type scenes and substituted stock sample footage,
   silently dropping the AI-generated visuals.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts import sound_manager  # noqa: E402
from scripts import story_pipeline as sp  # noqa: E402


IMG_SCENE = {
    "type": "image",
    "src": "/tmp/nonexistent_image.png",
    "durationInFrames": 90,
}
VID_SCENE = {
    "type": "video",
    "src": "/tmp/fake_stock_clip.mp4",
    "durationInFrames": 90,
}


def _wire_pipeline(monkeypatch, tmp_path, scenes, remotion_ok=False, converter=None):
    """Wires every collaborator of produce_story to offline fakes."""
    monkeypatch.setattr(sound_manager, "get_audio_assets_for_topic",
                        lambda *a, **k: {"mode": "commentary_speech", "music_src": None,
                                         "ambient_src": None, "use_original_audio": False,
                                         "music_volume": 0.0})
    monkeypatch.setattr(sp, "collect_scenes", lambda *a, **k: scenes)
    monkeypatch.setattr(sp, "make_voiceover",
                        lambda lines, out_dir: {"status": "SUCCESS", "file": None,
                                                "words": [], "voice": "test"})

    if remotion_ok:
        def fake_render(**kwargs):
            out = kwargs["output_mp4"]
            with open(out, "wb") as f:
                f.write(b"fake")
            return {"status": "SUCCESS", "file_path": out}
        monkeypatch.setattr(sp, "render_with_remotion", fake_render)
    else:
        monkeypatch.setattr(sp, "render_with_remotion",
                            lambda **k: {"status": "FAILED", "error": "simulated remotion failure"})

    monkeypatch.setattr(sp, "validate_video",
                        lambda p: {"status": "PASS", "width": 1080, "height": 1920,
                                   "duration_sec": 10.0, "codec": "h264", "has_audio": True})
    monkeypatch.setattr(sp, "generate_metadata", lambda topic: {"status": "SUCCESS"})
    monkeypatch.setattr(sp, "log_execution", lambda *a, **k: None)

    if converter is not None:
        monkeypatch.setattr(sp, "_convert_image_scene_to_clip", converter)

    commands = []

    class FakeProc:
        returncode = 0

    def fake_run(cmd, *args, **kwargs):
        commands.append(list(cmd))
        if cmd and cmd[0] == "bash" and len(cmd) > 2:
            with open(cmd[2], "wb") as f:
                f.write(b"fake")
        return FakeProc()

    monkeypatch.setattr(sp.subprocess, "run", fake_run)
    return commands


def test_fallback_converts_image_scenes(monkeypatch, tmp_path):
    """An image scene must reach the fallback as a converted clip, not sample.mp4."""
    fake_clip = str(tmp_path / "converted.png")

    def fake_convert(image_path, out_path, duration_sec, fps=30):
        assert image_path == IMG_SCENE["src"]
        with open(out_path, "wb") as f:
            f.write(b"clip")
        return out_path

    commands = _wire_pipeline(monkeypatch, tmp_path, [IMG_SCENE],
                              remotion_ok=False, converter=fake_convert)

    result = sp.produce_story("fallback topic", duration=10, logo=None, n_clips=1)
    assert result["status"] == "SUCCESS"
    assert result["steps"]["edit"]["engine"] == "ffmpeg_fallback"
    bash_cmd = next(c for c in commands if c and c[0] == "bash")
    assert any("fallback_scene_" in part for part in bash_cmd), bash_cmd
    assert not any(part.endswith("sample.mp4") for part in bash_cmd), bash_cmd


def test_fallback_sample_only_when_nothing_else(monkeypatch, tmp_path):
    """Only when no clip can be assembled at all does sample.mp4 step in."""
    commands = _wire_pipeline(monkeypatch, tmp_path, [IMG_SCENE],
                              remotion_ok=False, converter=lambda *a, **k: None)

    result = sp.produce_story("sample topic", duration=10, logo=None, n_clips=1)
    assert result["status"] == "SUCCESS"
    assert result["steps"]["edit"]["engine"] == "ffmpeg_fallback"
    bash_cmd = next(c for c in commands if c and c[0] == "bash")
    assert any(part.endswith("sample.mp4") for part in bash_cmd), bash_cmd


def test_remotion_success_keeps_engine_label(monkeypatch, tmp_path):
    """A successful Remotion render must still record the remotion engine."""
    called = []

    def spy_convert(*a, **k):
        called.append(a)
        return None

    commands = _wire_pipeline(monkeypatch, tmp_path, [IMG_SCENE],
                              remotion_ok=True, converter=spy_convert)

    result = sp.produce_story("remotion topic", duration=10, logo=None, n_clips=1)
    assert result["status"] == "SUCCESS"
    assert result["steps"]["edit"]["engine"] == "remotion"
    assert not called
    assert not any(c and c[0] == "bash" for c in commands)


def test_fallback_clip_paths_order(monkeypatch, tmp_path):
    """Mixed scenes come out in scene order: videos first-come, images converted."""
    def fake_convert(image_path, out_path, duration_sec, fps=30):
        with open(out_path, "wb") as f:
            f.write(b"clip")
        return out_path

    monkeypatch.setattr(sp, "_convert_image_scene_to_clip", fake_convert)
    stock = tmp_path / "stock.mp4"
    stock.write_bytes(b"clip")
    clips = sp._fallback_clip_paths(
        [IMG_SCENE, dict(VID_SCENE, src=str(stock)), IMG_SCENE],
        str(tmp_path))
    assert [os.path.basename(c) for c in clips] == [
        "fallback_scene_0.mp4", "stock.mp4", "fallback_scene_2.mp4"]


# --- Graceful-failure contract (Oct 15, 2026 audit) -------------------------
# The Remotion-failure fallback shells out to FFmpeg with timeout=900. A hung
# render raises subprocess.TimeoutExpired, which used to escape produce_story()
# uncaught, killing the whole continuous maker session. These tests pin the
# graceful-failure contract.


@pytest.fixture
def timeout_ready(monkeypatch):
    """Drive produce_story() to the Remotion-failure branch with everything
    else stubbed: no network, no real TTS, no real render."""
    monkeypatch.setenv("SHORTS_MOCK", "1")
    monkeypatch.setattr(sp, "classify_topic", lambda *a, **k: {
        "category": "tech", "style": "cinematic", "visual_mode": "stock",
        "music_mood": "calm_ambient", "badge_title": "TEST"})
    monkeypatch.setattr(sp, "write_script",
                        lambda *a, **k: {"lines": ["one", "two"], "writer": "test"})
    monkeypatch.setattr(sp, "make_voiceover",
                        lambda *a, **k: {"status": "SUCCESS", "file": None, "words": []})
    monkeypatch.setattr(sp, "collect_scenes", lambda *a, **k: [
        {"type": "video", "src": "/nonexistent/clip.mp4", "durationInFrames": 0}])
    monkeypatch.setattr(sp, "render_with_remotion",
                        lambda **k: {"status": "FAILED", "error": "simulated remotion failure"})
    monkeypatch.setattr(sound_manager, "get_audio_assets_for_topic", lambda *a, **k: {
        "mode": "commentary", "music_src": "/nonexistent/music.mp3",
        "music_volume": 0.2, "ambient_src": None, "ambient_volume": 0.6,
        "use_original_audio": False})


def test_fallback_render_timeout_returns_failed_not_crash(monkeypatch, timeout_ready):
    """A 900s timeout on the FFmpeg fallback render must return the FAILED dict
    (failed_step 'edit'), not raise TimeoutExpired out of produce_story()."""
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # silence.wav generation
            return subprocess.CompletedProcess(args=cmd, returncode=0)
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=900)

    monkeypatch.setattr(sp.subprocess, "run", fake_run)

    result = sp.produce_story("timeout topic", duration=30)
    assert result["status"] == "FAILED"
    assert result["failed_step"] == "edit"
    assert "timed out" in str(result.get("error", "")).lower()


def test_fallback_silence_failure_does_not_crash(monkeypatch, timeout_ready):
    """If even the silence track cannot be generated, the run must still come
    back as a clean FAILED result instead of an unhandled exception."""
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # silence.wav generation fails
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(sp.subprocess, "run", fake_run)

    result = sp.produce_story("silence topic", duration=30)
    assert result["status"] == "FAILED"
    assert result["failed_step"] == "edit"
