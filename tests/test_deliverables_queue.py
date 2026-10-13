import os
import json
import pytest
from unittest.mock import patch, MagicMock

from scripts.story_pipeline import run_story
import scripts.uploader as uploader


def test_story_pipeline_saves_deliverable_locally(sample_video, monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTS_MOCK", "1")
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    
    result = run_story("relaxing rain", duration=10, upload=False)
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "LOCAL"
    assert os.path.exists(result["deliverable_file"])
    assert result["deliverable_file"].endswith(".mp4")
    # Ensure json sidecar exists
    json_sidecar = result["deliverable_file"].rsplit(".", 1)[0] + ".json"
    assert os.path.exists(json_sidecar)


def test_story_pipeline_handles_youtube_quota_gracefully(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_MOCK", "1")
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    
    def fake_upload(*args, **kwargs):
        return {
            "status": "QUOTA_EXCEEDED",
            "error": "Daily quota limit reached",
            "quota_exceeded": True
        }

    monkeypatch.setattr(uploader, "upload_to_youtube", fake_upload)
    try:
        import run_pipeline
        monkeypatch.setattr(run_pipeline, "upload_to_youtube", fake_upload)
    except Exception:
        pass
    try:
        import scripts.run_pipeline as s_rp
        monkeypatch.setattr(s_rp, "upload_to_youtube", fake_upload)
    except Exception:
        pass

    result = run_story("ocean breeze", duration=10, upload=True)
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "LOCAL_QUEUE"
    assert os.path.exists(result["deliverable_file"])
