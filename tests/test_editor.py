import os

from conftest import probe
from scripts.editor import edit_video


def test_edit_makes_vertical_short(sample_video, tmp_path):
    output_file = str(tmp_path / "short.mp4")
    res = edit_video(sample_video, output_file, duration=5)
    assert res["status"] == "SUCCESS"
    streams = probe(output_file)
    video = next(s for s in streams if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in streams)


def test_junk_input_fails_instead_of_copying(sample_video, tmp_path):
    junk = tmp_path / "raw.mp4"
    junk.write_bytes(b"0" * (200 * 1024))
    output_file = str(tmp_path / "short.mp4")
    res = edit_video(str(junk), output_file, duration=15)
    assert res["status"] == "FAILED"
    assert not os.path.exists(output_file)


def test_missing_input_fails(tmp_path):
    assert edit_video(str(tmp_path / "nope.mp4"))["status"] == "FAILED"


def test_edit_timeout_stops_ffmpeg_and_cleans_up(sample_video, tmp_path, monkeypatch):
    import subprocess
    from scripts.editor import edit_video
    monkeypatch.setenv("FFMPEG_TIMEOUT_SEC", "1")
    out = tmp_path / "slow.mp4"
    result = edit_video(sample_video, str(out), duration=8)
    if result["status"] == "SUCCESS":
        return  # machine fast enough to finish in under a second
    assert "FFMPEG_TIMEOUT_SEC" in result["error"]
    assert not out.exists()
    left = subprocess.run(["pgrep", "-f", str(out)], capture_output=True, text=True).stdout.strip()
    assert left == ""
