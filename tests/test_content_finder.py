from scripts import content_finder
from scripts.content_finder import find_videos, rank_and_select_video, search_pexels, search_pixabay


def test_mock_mode_returns_local_sample():
    candidate = rank_and_select_video(find_videos("nature"))
    assert candidate is not None
    assert candidate["video_url"].startswith("file://")


def test_no_keys_and_no_mock_finds_nothing(monkeypatch):
    monkeypatch.delenv("SHORTS_MOCK")
    assert find_videos("nature") == []


def test_placeholder_key_is_ignored(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "your_pexels_api_key_here")
    assert search_pexels("nature") == []


def test_pexels_query_is_url_encoded(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=10):
        seen["url"], seen["headers"] = url, headers
        return {"videos": []}

    monkeypatch.setenv("PEXELS_API_KEY", "real-key")
    monkeypatch.setattr(content_finder, "_get_json", fake_get)
    search_pexels("ocean waves & sand")
    assert "query=ocean+waves+%26+sand" in seen["url"]
    assert seen["headers"] == {"Authorization": "real-key"}


def test_pixabay_results_are_normalised(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "real-key")
    monkeypatch.setattr(content_finder, "_get_json", lambda url, headers=None, timeout=10: {
        "hits": [{"id": 7, "duration": 20, "user": "ana", "videos": {
            "large": {"url": "https://x/large.mp4", "width": 1920, "height": 1080},
            "small": {"url": "https://x/small.mp4", "width": 960, "height": 540},
        }}]
    })
    videos = search_pixabay("rain")
    assert videos[0]["id"] == "pixabay_7"
    assert rank_and_select_video(videos)["video_url"] == "https://x/large.mp4"


def test_ranking_prefers_portrait_up_to_1920():
    videos = [{
        "id": 1, "duration": 25, "user": {"name": "a"},
        "video_files": [
            {"width": 2160, "height": 3840, "link": "4k"},
            {"width": 1080, "height": 1920, "link": "hd"},
            {"width": 1920, "height": 1080, "link": "landscape"},
        ],
    }]
    assert rank_and_select_video(videos)["video_url"] == "hd"


def test_ranking_rejects_wrong_lengths():
    videos = [{"id": 1, "duration": 300, "video_files": [{"width": 1080, "height": 1920, "link": "x"}]}]
    assert rank_and_select_video(videos) is None
    assert rank_and_select_video([]) is None
