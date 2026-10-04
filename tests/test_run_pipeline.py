import os

from scripts.run_pipeline import run


def test_run_pipeline_mock_end_to_end(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    result = run("ocean", duration=5)
    assert result["status"] == "SUCCESS", result
    assert result["mode"] == "MOCK"
    assert result["privacy"] == "private"
    assert result["steps"]["validate_edited"]["height"] == 1920
    assert result["steps"]["validate_edited"]["width"] == 1080
    assert os.path.exists(result["steps"]["archive"]["archived_edited"])


def test_run_pipeline_without_keys_fails_clearly(monkeypatch):
    monkeypatch.delenv("SHORTS_MOCK")
    result = run("ocean", duration=5)
    assert result["status"] == "FAILED"
    assert result["failed_step"] == "find"
    assert "PEXELS_API_KEY" in result["error"]
