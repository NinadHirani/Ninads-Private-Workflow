"""
Tests for Continuous Episodic Series Video Engine:
- Series state management and persistent campaign tracking
- Character sheet, gear, injuries, and era transitions
- Procedural & LLM script writing with cliffhanger continuity
- Remotion episodic rendering with batch season generation
"""

import os
import sys
import json
import shutil
import tempfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import series_manager, series_writer, series_pipeline


@pytest.fixture
def temp_series_dir(monkeypatch):
    """Isolates series storage into a temporary directory."""
    temp_dir = tempfile.mkdtemp(prefix="test_series_root_")
    monkeypatch.setattr(series_manager, "SERIES_ROOT", temp_dir)
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_series_init_and_load(temp_series_dir):
    st = series_manager.init_series("test_kane", preset="kane")
    assert st["series_id"] == "test_kane"
    assert st["current_episode"] == 1
    assert st["timeline_day"] == 1
    assert st["character"]["name"] == "Kane"

    loaded = series_manager.load_series("test_kane")
    assert loaded is not None
    assert loaded["series_id"] == "test_kane"
    assert loaded["current_episode"] == 1


def test_series_continuity_context(temp_series_dir):
    st = series_manager.init_series("test_ctx", preset="kane")
    ctx = series_manager.format_continuity_context(st)
    assert ctx["episode_number"] == 1
    assert ctx["timeline_day"] == 1
    assert ctx["character_name"] == "Kane"
    assert "Kane" in ctx["character_identity"]
    assert ctx["last_cliffhanger"] == "None (Beginning of journey)"


def test_series_advance_and_era_transition(temp_series_dir):
    st = series_manager.init_series("test_advance", preset="kane")
    summary_ep1 = {
        "title": "The First Breath",
        "summary": "Kane survived the first ash wave.",
        "cliffhanger": "A metallic screech sounded beneath the subway floor.",
        "days_passed": 2,
        "new_wounds": "Bandaged right knee",
    }
    updated = series_manager.advance_series("test_advance", summary_ep1)
    assert updated["current_episode"] == 2
    assert updated["timeline_day"] == 3
    assert updated["last_cliffhanger"] == "A metallic screech sounded beneath the subway floor."
    assert updated["character"]["physical_condition"] == "Bandaged right knee"
    assert len(updated["episode_history"]) == 1

    # Simulate advancing past Era 1 duration (12 episodes)
    for ep in range(2, 14):
        series_manager.advance_series("test_advance", {
            "title": f"Episode {ep}",
            "summary": f"Summary {ep}",
            "cliffhanger": f"Cliffhanger {ep}",
            "days_passed": 1
        })
    advanced = series_manager.load_series("test_advance")
    assert advanced["current_episode"] == 14
    assert advanced["current_era_index"] == 1  # Transitioned to Era 2


def test_procedural_series_writer(temp_series_dir):
    st = series_manager.init_series("test_writer", preset="kane")
    ctx = series_manager.format_continuity_context(st)
    ep_data = series_writer.generate_procedural_series_episode(ctx)

    assert "script_lines" in ep_data
    assert len(ep_data["script_lines"]) >= 5
    assert "cliffhanger" in ep_data
    assert len(ep_data["cliffhanger"]) > 5
    assert len(ep_data["scene_prompts"]) == 4
    for p in ep_data["scene_prompts"]:
        assert "Kane" in p
        assert "vertical 9:16" in p


def test_mock_produce_episode_and_batch(monkeypatch, temp_series_dir):
    monkeypatch.setenv("SHORTS_MOCK", "1")

    # Produce Episode 1
    ep1_res = series_pipeline.produce_episode(series_id="mock_kane", preset="kane")
    assert ep1_res["status"] == "SUCCESS"
    assert ep1_res["episode"] == 1
    assert os.path.exists(ep1_res["video_file"])
    assert os.path.exists(ep1_res["metadata_file"])

    st = series_manager.load_series("mock_kane")
    assert st["current_episode"] == 2
    assert st["last_cliffhanger"] == ep1_res["cliffhanger"]

    # Produce Batch of 2 more episodes (Episodes 2 & 3)
    batch_res = series_pipeline.produce_batch(series_id="mock_kane", count=2)
    assert len(batch_res) == 2
    assert batch_res[0]["episode"] == 2
    assert batch_res[1]["episode"] == 3

    st_after = series_manager.load_series("mock_kane")
    assert st_after["current_episode"] == 4
    assert len(st_after["episode_history"]) == 3
