import os
import pytest
from scripts.scene_generator import classify_topic
from scripts.sound_manager import get_audio_assets_for_topic, check_video_audio_track
from scripts.metadata_generator import generate_metadata


def test_classify_topic_anime_scene():
    res = classify_topic("Saitama vs Boros fight scene")
    assert res["category"] == "anime_scene"
    assert res["audio_mode"] == "original_voice"
    assert res["style"] == "anime"

    res2 = classify_topic("Naruto epic battle moment")
    assert res2["category"] == "anime_scene"
    assert res2["audio_mode"] == "original_voice"


def test_classify_topic_anime_commentary():
    res = classify_topic("Why Saitama broke anime rules")
    assert res["category"] == "anime"
    assert res["audio_mode"] == "commentary_speech"


def test_classify_topic_movie_scene():
    res = classify_topic("Batman interrogation movie scene")
    assert res["category"] == "movie_scene"
    assert res["audio_mode"] == "original_voice"

    res2 = classify_topic("Oppenheimer dramatic scene")
    assert res2["category"] == "movie_scene"
    assert res2["audio_mode"] == "original_voice"


def test_classify_topic_non_scenes():
    # Stoic Wisdom
    stoic = classify_topic("Marcus Aurelius on controlling your mind")
    assert stoic["category"] == "stoic"
    assert stoic["audio_mode"] == "commentary_speech"

    # Dark Psychology Facts
    facts = classify_topic("Dark psychological fact about silence")
    assert facts["category"] == "facts_mystery"
    assert facts["audio_mode"] == "commentary_speech"

    # Future AI / Tech
    tech = classify_topic("How AI will change human memory forever")
    assert tech["category"] == "tech_ai"
    assert tech["audio_mode"] == "commentary_speech"

    # Nature ASMR
    nature = classify_topic("relaxing rain on green leaves")
    assert nature["category"] == "nature"
    assert nature["audio_mode"] == "nature_asmr"


def test_get_audio_assets_for_topic():
    # Anime/Movie scene
    scene_cfg = get_audio_assets_for_topic("Gojo vs Sukuna fight scene", "anime_scene", "epic_anime")
    assert scene_cfg["mode"] == "original_voice"
    assert scene_cfg["voiceover_required"] is False
    assert scene_cfg["use_original_audio"] is True
    assert scene_cfg["video_volume"] == 1.0

    # Commentary mode
    commentary_cfg = get_audio_assets_for_topic("Marcus Aurelius", "stoic", "cinematic_epic")
    assert commentary_cfg["mode"] == "commentary_speech"
    assert commentary_cfg["voiceover_required"] is True
    assert commentary_cfg["use_original_audio"] is False
    assert commentary_cfg["video_volume"] == 0.0
    assert commentary_cfg["music_src"] is not None

    # Nature ASMR mode
    nature_cfg = get_audio_assets_for_topic("rain", "nature", "calm_ambient")
    assert nature_cfg["mode"] == "nature_asmr"
    assert nature_cfg["voiceover_required"] is False
    assert nature_cfg["use_original_audio"] is True
    assert nature_cfg["ambient_src"] is not None


def test_get_audio_assets_override():
    override_cfg = get_audio_assets_for_topic("Any topic", "stoic", override_mode="original_voice")
    assert override_cfg["mode"] == "original_voice"
    assert override_cfg["use_original_audio"] is True
    assert override_cfg["voiceover_required"] is False


def test_check_video_audio_track(sample_video):
    info = check_video_audio_track(sample_video)
    assert isinstance(info, dict)
    assert "has_audio" in info
    assert "has_audible_sound" in info


def test_metadata_for_scenes():
    anime_meta = generate_metadata("Saitama vs Boros fight scene")
    assert "anime" in anime_meta["tags"]
    assert any("original" in t or "scene" in t for t in anime_meta["tags"])

    movie_meta = generate_metadata("Batman movie scene")
    assert "movie" in movie_meta["tags"]


def test_story_pipeline_original_voice_mode(sample_video, monkeypatch):
    monkeypatch.setenv("SHORTS_MOCK", "1")
    monkeypatch.setenv("SHORTS_SAMPLE_VIDEO", sample_video)
    from scripts.story_pipeline import produce_story
    prod = produce_story("Saitama vs Boros fight scene", duration=10, n_clips=2)
    assert prod["status"] == "SUCCESS"
    assert prod["steps"]["audio_mode"] == "original_voice"
    assert prod["steps"]["voiceover"]["words"] == 0
    assert os.path.exists(prod["edited_path"])
