import os

from scripts.archive import archive_processed_media
from scripts.content_finder import find_videos, rank_and_select_video
from scripts.downloader import download_video
from scripts.editor import edit_video
from scripts.logger import log_execution
from scripts.metadata_generator import generate_metadata
from scripts.uploader import upload_to_youtube
from scripts.validator import validate_video


def test_full_pipeline_end_to_end(sample_video, tmp_path):
    topic = "ocean"

    candidate = rank_and_select_video(find_videos(topic))
    assert candidate is not None

    raw_path = str(tmp_path / "raw_test.mp4")
    assert download_video(candidate["video_url"], raw_path, retries=2, timeout=10)["status"] == "SUCCESS"
    assert validate_video(raw_path)["status"] == "PASS"

    edited_path = str(tmp_path / "edited_test.mp4")
    assert edit_video(raw_path, edited_path, duration=5)["status"] == "SUCCESS"
    assert validate_video(edited_path)["height"] == 1920

    meta = generate_metadata(topic)
    upload_res = upload_to_youtube(edited_path, title=meta["title"], description=meta["description"], tags=meta["tags"])
    assert upload_res["status"] == "SUCCESS"

    log_res = log_execution(topic, upload_res["status"], os.path.basename(edited_path), upload_res["video_id"], upload_res["youtube_url"])
    assert log_res["status"] == "SUCCESS"

    arch = archive_processed_media(raw_path, edited_path)
    assert arch["archived_raw"] and arch["archived_edited"]
    assert not os.path.exists(raw_path)
