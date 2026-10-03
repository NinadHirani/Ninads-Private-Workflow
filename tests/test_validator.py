import subprocess

from scripts import validator
from scripts.validator import validate_video


def test_missing_file_fails():
    assert validate_video("non_existent_file.mp4")["status"] == "FAIL"


def test_junk_bytes_fail(tmp_path):
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"0" * (200 * 1024))
    assert validate_video(str(junk))["status"] == "FAIL"


def test_missing_ffprobe_fails(tmp_path, monkeypatch):
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"0" * (200 * 1024))

    def no_ffprobe(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr(validator.subprocess, "run", no_ffprobe)
    res = validate_video(str(junk))
    assert res["status"] == "FAIL"
    assert "ffprobe" in res["reason"]


def test_real_video_passes(sample_video):
    res = validate_video(sample_video)
    assert res["status"] == "PASS"
    assert (res["width"], res["height"]) == (1280, 720)
    assert res["has_audio"] is True
    assert res["orientation"] == "landscape"
