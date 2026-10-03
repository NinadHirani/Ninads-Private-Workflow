import os
import sys
import shutil
import tempfile
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Keep test output out of the real downloads/, edited/, archive/ and logs/ folders.
_WORK = tempfile.mkdtemp(prefix="shorts_tests_")
for _name, _dir in (("DOWNLOAD_PATH", "downloads"), ("EDIT_PATH", "edited"), ("ARCHIVE_PATH", "archive"), ("LOG_PATH", "logs")):
    os.environ[_name] = os.path.join(_WORK, _dir)

SAMPLE = os.path.join(os.path.dirname(__file__), "sample.mp4")
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Tests never touch real APIs: no keys, mock mode on unless a test turns it off."""
    for key in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SHORTS_MOCK", "1")


@pytest.fixture(scope="session")
def sample_video():
    """An 8s 1280x720 clip with a tone, generated once (needs FFmpeg)."""
    if not HAVE_FFMPEG:
        pytest.skip("FFmpeg is not installed")
    if not os.path.exists(SAMPLE):
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=8",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", SAMPLE,
            ],
            check=True,
        )
    return SAMPLE


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", path],
        capture_output=True, text=True, check=True,
    ).stdout
    import json
    return json.loads(out)["streams"]
