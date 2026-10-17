import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.script_archetypes import (
    ARCHETYPES,
    EMOTIONAL_TONES,
    detect_language,
    auto_select_matrix,
    calculate_pacing_targets,
    build_system_prompt,
    generate_combinatorial_script,
)
from scripts.script_writer import write_script


def test_detect_language():
    assert detect_language("Marcus Aurelius Stoic Mindset") == "english"
    assert detect_language("Bhai ye sunkar dimaag hil jayega") == "hinglish"
    assert detect_language("Desi jugaad for high productivity") == "hinglish"
    assert detect_language("मन की शांति के लिए रहस्य") == "hindi"


def test_auto_select_matrix():
    # Hindi/Hinglish topic
    m1 = auto_select_matrix("Bhai ye kya khatarnak trick hai")
    assert m1["archetype"] == "indian_brainrot"
    assert m1["emotion"] == "desi_brainrot"
    assert m1["language"] == "hinglish"

    # Stoic topic
    m2 = auto_select_matrix("Marcus Aurelius on controlling your mind", category="stoic")
    assert m2["archetype"] == "deep_reflection"
    assert m2["emotion"] == "stoic_grounded"

    # Mystery / Paradox topic
    m3 = auto_select_matrix("The dark paradox of human consciousness", category="facts_mystery")
    assert m3["archetype"] == "paradox_mystery"
    assert m3["emotion"] == "suspenseful_dark"


def test_pacing_targets():
    p15 = calculate_pacing_targets(15)
    assert p15["min_lines"] >= 3
    assert p15["max_lines"] <= 5
    assert p15["target_words"] <= 45

    p45 = calculate_pacing_targets(45)
    assert p45["min_lines"] >= 6
    assert p45["max_lines"] <= 9
    assert p45["target_words"] > 80

    p60 = calculate_pacing_targets(60)
    assert p60["min_lines"] >= 8
    assert p60["max_lines"] <= 12
    assert p60["target_words"] >= 130


def test_build_system_prompt():
    prompt = build_system_prompt(
        topic="The Fermi Paradox",
        archetype_key="paradox_mystery",
        emotion_key="suspenseful_dark",
        duration=30,
        language="english"
    )
    assert "The Fermi Paradox" in prompt
    assert "Curiosity Paradox" in prompt
    assert "JSON array of strings" in prompt


def test_generate_combinatorial_script():
    # English narrative
    lines_en = generate_combinatorial_script("Quantum Leap", "narrative_story", duration=45, language="english")
    assert isinstance(lines_en, list)
    assert len(lines_en) >= 4
    assert any("Quantum Leap" in line for line in lines_en)

    # Hinglish brainrot
    lines_hi = generate_combinatorial_script("Robot invasion", "indian_brainrot", duration=30, language="hinglish")
    assert isinstance(lines_hi, list)
    assert len(lines_hi) >= 4
    assert any("Robot Invasion" in line or "Bhai" in line or "dimaag" in line for line in lines_hi)


def test_write_script_end_to_end():
    # Without keys, it falls back to combinatorial script with valid structure
    res = write_script("The Mind Paradox", duration=30)
    assert res["status"] == "SUCCESS"
    assert len(res["lines"]) >= 3
    assert res["archetype"] in ARCHETYPES
    assert res["emotion"] in EMOTIONAL_TONES
