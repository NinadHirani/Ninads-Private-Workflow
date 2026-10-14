import os
import tempfile
import pytest

from scripts.logger import mark_asset_used, is_asset_used, mark_topic_used, is_topic_used, get_used_asset_ids
from scripts.content_finder import rank_and_select_video
from scripts.archive import delete_processed_media
from scripts import purge_and_index as pni
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


def _plant(root, rel, name, content=b"x"):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(content)
    return p


def test_purge_media_dry_run_deletes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(pni, "ROOT", str(tmp_path))
    keep = _plant(tmp_path, "downloads", "raw_1.mp4")
    keep_json = _plant(tmp_path, "deliverables", "short_1.json")
    res = purge_media(dry_run=True)
    assert res["dry_run"] is True
    assert res["deleted_count"] >= 2
    assert keep.exists() and keep_json.exists()


def test_purge_media_deletes_media_preserves_specials(monkeypatch, tmp_path):
    monkeypatch.setattr(pni, "ROOT", str(tmp_path))
    media = _plant(tmp_path, "edited", "short_1.mp4")
    meta = _plant(tmp_path, "deliverables", "short_1.json")
    gitkeep = _plant(tmp_path, "downloads", ".gitkeep")
    hidden = _plant(tmp_path, "archive", ".DS_Store")
    logo = _plant(tmp_path, "archive", "my_logo.png")
    other = _plant(tmp_path, "archive", "notes.txt")

    res = purge_media(dry_run=False)
    assert res["dry_run"] is False
    assert not media.exists() and not meta.exists()
    assert gitkeep.exists()
    assert hidden.exists()
    assert logo.exists()
    assert other.exists()


def test_purge_scenes_dir_same_protections(monkeypatch, tmp_path):
    """The remotion scenes cleanup once deleted EVERY file in the folder,
    dotfiles and non-media included. It must follow the same rules as the
    main purge loop."""
    monkeypatch.setattr(pni, "ROOT", str(tmp_path))
    scene = _plant(tmp_path, "remotion/public/scenes", "scene1.png")
    gitkeep = _plant(tmp_path, "remotion/public/scenes", ".gitkeep")
    cfg = _plant(tmp_path, "remotion/public/scenes", "webpack.config.js")

    purge_media(dry_run=False)
    assert not scene.exists()
    assert gitkeep.exists() and cfg.exists()
