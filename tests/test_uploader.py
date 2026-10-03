import json

from scripts.uploader import load_metadata, upload_to_youtube


def _video(tmp_path):
    path = tmp_path / "short.mp4"
    path.write_bytes(b"0" * 1024)
    return str(path)


def test_mock_upload(tmp_path):
    res = upload_to_youtube(_video(tmp_path), title="Test Short", privacy_status="unlisted")
    assert res["status"] == "SUCCESS"
    assert res["mode"] == "MOCK"


def test_missing_credentials_fail_instead_of_faking(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTS_MOCK")
    res = upload_to_youtube(_video(tmp_path))
    assert res["status"] == "FAILED"
    assert "credentials" in res["error"]


def test_placeholder_credentials_fail(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTS_MOCK")
    for key in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(key, f"your_{key.lower()}_here")
    assert upload_to_youtube(_video(tmp_path))["status"] == "FAILED"


def test_bad_privacy_and_missing_file(tmp_path):
    assert upload_to_youtube(_video(tmp_path), privacy_status="everyone")["status"] == "FAILED"
    assert upload_to_youtube(str(tmp_path / "none.mp4"))["status"] == "FAILED"


def test_load_metadata(tmp_path):
    path = tmp_path / "meta.json"
    path.write_text(json.dumps({"title": "T", "description": "D", "tags": ["a"], "status": "SUCCESS"}))
    assert load_metadata(str(path)) == {"title": "T", "description": "D", "tags": ["a"]}
