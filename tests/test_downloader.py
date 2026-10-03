import os

from scripts.downloader import download_video


def test_download_local_file(sample_video, tmp_path):
    output_file = str(tmp_path / "test_raw.mp4")
    res = download_video(f"file://{sample_video}", output_file, retries=2, timeout=10)
    assert res["status"] == "SUCCESS"
    assert os.path.getsize(output_file) == os.path.getsize(sample_video)


def test_download_failure(tmp_path):
    res = download_video("file:///no/such/video.mp4", str(tmp_path / "fail.mp4"), retries=1, timeout=2)
    assert res["status"] == "FAILED"
