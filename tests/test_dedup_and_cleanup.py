import os
import tempfile
import pytest

from scripts.logger import mark_asset_used, is_asset_used, mark_topic_used, is_topic_used, get_used_asset_ids
from scripts.content_finder import rank_and_select_video
from scripts.archive import delete_processed_media
from scripts.purge_and_index import purge_media


def test_asset_deduplication():
    test_id = f"test_vid_{os.urandom(4).hex()}"
    assert not is_asset_used(test_id)
    mark_asset_used(test_id, provider="pexels", topic="ocean waves")
    assert is_asset_used(test_id)
    assert test_id in get_used_asset_ids()


def test_topic_deduplication():
    test_topic = f"Unique Sunset Topic {os.urandom(4).hex()}"
    assert not is_topic_used(test_topic)
    mark_topic_used(test_topic)
    assert is_topic_used(test_topic)
    # Case insensitivity & normalization
    assert is_topic_used(test_topic.lower())


def test_rank_and_select_skips_used_assets():
    vid_1 = {"id": "pexels_1001", "duration": 25, "video_files": [{"width": 1080, "height": 1920, "link": "https://vid1.mp4"}]}
    vid_2 = {"id": "pexels_1002", "duration": 25, "video_files": [{"width": 1080, "height": 1920, "link": "https://vid2.mp4"}]}

    # Initially both are available, picks vid_1
    cand = rank_and_select_video([vid_1, vid_2], exclude_used=False)
    assert cand["video_id"] == "pexels_1001"

    # Mark vid_1 as used
    mark_asset_used("pexels_1001")
    # Now it must skip vid_1 and pick vid_2
    cand_fresh = rank_and_select_video([vid_1, vid_2], exclude_used=True)
    assert cand_fresh["video_id"] == "pexels_1002"


def test_delete_processed_media(tmp_path):
    f1 = tmp_path / "raw.mp4"
    f2 = tmp_path / "edited.mp4"
    f1.write_text("dummy")
    f2.write_text("dummy")
    assert f1.exists() and f2.exists()

    res = delete_processed_media(raw_path=str(f1), edited_path=str(f2))
    assert res["status"] == "SUCCESS"
    assert not f1.exists()
    assert not f2.exists()
