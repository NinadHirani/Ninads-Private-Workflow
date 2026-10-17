#!/usr/bin/env python3
"""
Series Manager - AI Shorts Factory
Manages persistent state, character sheets, continuous era evolution,
inventory, injuries, and cliffhanger handoffs for infinite episodic series.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("series_manager")
try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES_ROOT = os.path.join(ROOT, "series")


# Built-in Flagship Series Archetypes
DEFAULT_PRESETS: Dict[str, Dict[str, Any]] = {
    "kane": {
        "title": "The Last Wanderer: Kane's Chronicles",
        "genre": "gritty_survival",
        "voice": "en-US-ChristopherNeural",
        "style": "cinematic",
        "character": {
            "name": "Kane",
            "archetype": "lone survivor",
            "visual_identity": (
                "Kane, a weathered 32-year-old lone survivor, short dark disheveled hair, "
                "jagged scar across left brow, tactical charcoal-olive jacket with reinforced "
                "stitched canvas patches, fingerless leather gloves, rugged military backpack "
                "with red climbing carabiner and worn bedroll"
            ),
            "signature_gear": "serrated combat blade, cracked handheld Geiger counter, dented brass lighter",
            "physical_condition": "Right shoulder bound with weather-stained linen, cautious alert posture",
            "mental_state": "hyper-vigilant, grim resolve, deeply knowledgeable in wasteland survival",
        },
        "eras": [
            {
                "name": "Era 1: The Ash Fall",
                "subtitle": "The Initial Collapse",
                "description": "Global skies choked by volcanic ash and orbital debris. Cities are silent husks, and blind subterranean predators hunt by acoustic vibration.",
                "visual_palette": "charcoal gray, toxic orange ember glow, thick volumetric ash fog, decaying brutalist skyscrapers, 35mm film grain, 8k cinematic realism",
                "duration_episodes": 12,
            },
            {
                "name": "Era 2: The Sunken Grid",
                "subtitle": "Subterranean Exodus",
                "description": "Surface freezes over. Survivors descend into flooded metro transit catacombs, battling bioluminescent aquatic mutants and ruthless scavenger cults.",
                "visual_palette": "deep murky teal, bioluminescent cyan fungi, rusted train cars, dripping industrial pipes, underwater flares",
                "duration_episodes": 15,
            },
            {
                "name": "Era 3: The Celestial Rupture",
                "subtitle": "The Anomaly",
                "description": "A shattered alien monolith impacts the continent. Reality fractures with shifting localized gravity, crystalline fauna, and mysterious spatial rifts.",
                "visual_palette": "violet starlight, levitating obsidian monoliths, shimmering spatial distortions, electric purple mist",
                "duration_episodes": 20,
            },
            {
                "name": "Era 4: The Iron Ascendance",
                "subtitle": "Rise of the Machines",
                "description": "Dormant pre-war autonomous war complexes reboot without human oversight. Autonomous hunter-striders and lethal search-drones scour the wasteland.",
                "visual_palette": "cold brushed steel, laser crimson optic sensors, blinding searchlight beams in rain, high-tech ruins",
                "duration_episodes": 25,
            },
        ],
    },
    "goliath": {
        "title": "Goliath: The Subterranean Beast",
        "genre": "monster_odyssey",
        "voice": "en-US-GuyNeural",
        "style": "cinematic",
        "character": {
            "name": "Goliath",
            "archetype": "ancient stone beast",
            "visual_identity": (
                "towering quad-horned stone golem beast with glowing amber magma veins pulsing through cracked granite hide, "
                "moss-covered rocky shoulders, glowing molten eyes, ancient runic carved markings"
            ),
            "signature_gear": "chipped obsidian battle club, chest bound in massive iron chain link",
            "physical_condition": "Right stone horn partially severed in ancient battle, immense brute mass",
            "mental_state": "primordial intelligence, protective of subterranean wildlife, wary of surface human incursions",
        },
        "eras": [
            {
                "name": "Era 1: The Awakening",
                "subtitle": "The Tremor",
                "description": "Deep beneath the earth, tectonic fracking shatters Goliath's thousand-year slumber. He must navigate collapsing magma caverns and surface drilling rigs.",
                "visual_palette": "subterranean magma orange, obsidian rock, glowing sulfur steam, colossal cave caverns",
                "duration_episodes": 10,
            },
            {
                "name": "Era 2: The Surface Breach",
                "subtitle": "The Lost Sun",
                "description": "Goliath surfaces into a ruined human city overrun by mutant megafauna, claiming territory against rival apex titan predators.",
                "visual_palette": "ruined overgrown skyscrapers, tangled roots, stormy twilight sky, titan scale perspective",
                "duration_episodes": 15,
            },
        ],
    },
    "zero_stickman": {
        "title": "Zero: The Wasteland Ronin",
        "genre": "stylized_action",
        "voice": "en-GB-RyanNeural",
        "style": "anime",
        "character": {
            "name": "Zero",
            "archetype": "stickman assassin",
            "visual_identity": (
                "stylized high-contrast pitch-black stickman warrior, glowing crimson visor slit, "
                "tattered red katana scabbard on back, twin thermal throwing daggers, dynamic motion silhouette"
            ),
            "signature_gear": "plasma-edge katana, smoke dispersion pellets, grapple wire",
            "physical_condition": "Flawless reflexes, crackling electrical static around hands",
            "mental_state": "stoic, deadly precision, hunting the cybernetic warlords who burned his clan",
        },
        "eras": [
            {
                "name": "Era 1: Neon Bloodshed",
                "subtitle": "The Hunt Begins",
                "description": "Hunting bounty targets through rain-slicked cyberpunk slums and toxic industrial alleyways.",
                "visual_palette": "high contrast black silhouettes, vibrant neon red and cyan backlights, speedline motion blur",
                "duration_episodes": 15,
            },
        ],
    },
}


def get_series_dir(series_id: str) -> str:
    """Returns absolute path to a series workspace."""
    clean_id = "".join(c for c in series_id.lower() if c.isalnum() or c in ("_", "-")).strip("_") or "kane"
    return os.path.join(SERIES_ROOT, clean_id)


def load_series(series_id: str) -> Optional[Dict[str, Any]]:
    """Loads state.json for a series, or returns None if it doesn't exist."""
    s_dir = get_series_dir(series_id)
    state_file = os.path.join(s_dir, "state.json")
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load series state from %s: %s", state_file, redact(str(exc)))
        return None


def save_series(series_id: str, state: Dict[str, Any]) -> bool:
    """Saves state.json safely with atomic write."""
    s_dir = get_series_dir(series_id)
    os.makedirs(s_dir, exist_ok=True)
    state_file = os.path.join(s_dir, "state.json")
    tmp_file = f"{state_file}.tmp.{int(time.time() * 1000)}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, state_file)
        return True
    except Exception as exc:
        logger.error("Failed to save series state to %s: %s", state_file, redact(str(exc)))
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        return False


def init_series(series_id: str, preset: str = "kane", custom_title: Optional[str] = None) -> Dict[str, Any]:
    """Initializes a new series from a preset or default template."""
    existing = load_series(series_id)
    if existing:
        return existing

    cfg = DEFAULT_PRESETS.get(preset.lower(), DEFAULT_PRESETS["kane"])
    state = {
        "series_id": series_id,
        "title": custom_title or cfg["title"],
        "genre": cfg["genre"],
        "voice": cfg["voice"],
        "style": cfg["style"],
        "current_episode": 1,
        "timeline_day": 1,
        "current_era_index": 0,
        "character": cfg["character"],
        "eras": cfg["eras"],
        "world_state": {
            "location": "Sector 4 Ruined Transit Hub",
            "weather": "Dense toxic ash fall, waning daylight",
            "threat": "Subterranean acoustic crawlers active in shadows",
        },
        "last_cliffhanger": None,
        "episode_history": [],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_series(series_id, state)
    logger.info("Initialized new series '%s' with preset '%s'", series_id, preset)
    return state


def get_current_era(state: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieves current active era, advancing index if episode threshold is passed."""
    eras = state.get("eras") or []
    if not eras:
        return {
            "name": "Era 1: The Wasteland",
            "subtitle": "Survival",
            "description": "Desolate landscape of ruin and survival.",
            "visual_palette": "photorealistic, cinematic, gritty post-apocalyptic",
        }
    idx = state.get("current_era_index", 0)
    if idx >= len(eras):
        idx = len(eras) - 1
    return eras[idx]


def format_continuity_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds rich continuity context for the LLM writer and visual prompt builder.
    """
    ep_num = state.get("current_episode", 1)
    day_num = state.get("timeline_day", 1)
    era = get_current_era(state)
    char = state.get("character", {})
    world = state.get("world_state", {})
    last_cliff = state.get("last_cliffhanger")
    history = state.get("episode_history", [])

    recent_recaps = []
    for h in history[-3:]:
        recent_recaps.append(f"- Episode {h.get('episode')}, Day {h.get('day')}: {h.get('summary', '')}")

    recap_str = "\n".join(recent_recaps) if recent_recaps else "None (This is the pilot premiere)."

    return {
        "series_id": state.get("series_id"),
        "series_title": state.get("title"),
        "episode_number": ep_num,
        "timeline_day": day_num,
        "era_name": era.get("name"),
        "era_subtitle": era.get("subtitle"),
        "era_description": era.get("description"),
        "visual_palette": era.get("visual_palette"),
        "character_name": char.get("name"),
        "character_identity": char.get("visual_identity"),
        "character_gear": char.get("signature_gear"),
        "character_wounds": char.get("physical_condition"),
        "character_mindset": char.get("mental_state"),
        "location": world.get("location"),
        "weather": world.get("weather"),
        "threat": world.get("threat"),
        "last_cliffhanger": last_cliff or "None (Beginning of journey)",
        "recent_history_recap": recap_str,
    }


def advance_series(series_id: str, episode_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advances series state after an episode is produced:
    - Increments episode count and timeline day
    - Updates character wounds / gear / location
    - Sets new cliffhanger for the next episode
    - Checks for era evolution
    """
    state = load_series(series_id)
    if not state:
        raise ValueError(f"Series '{series_id}' does not exist.")

    ep_num = state.get("current_episode", 1)
    day_num = state.get("timeline_day", 1)

    # Days passed in this episode (default 1 to 3 days)
    days_passed = max(1, int(episode_summary.get("days_passed", 1)))
    new_day = day_num + days_passed

    # Update world / character state if specified
    if episode_summary.get("new_location"):
        state["world_state"]["location"] = episode_summary["new_location"]
    if episode_summary.get("new_threat"):
        state["world_state"]["threat"] = episode_summary["new_threat"]
    if episode_summary.get("new_wounds"):
        state["character"]["physical_condition"] = episode_summary["new_wounds"]
    if episode_summary.get("new_gear"):
        state["character"]["signature_gear"] = episode_summary["new_gear"]

    # Save to history
    record = {
        "episode": ep_num,
        "day": day_num,
        "title": episode_summary.get("title", f"Episode {ep_num}"),
        "era": state.get("eras", [{}])[state.get("current_era_index", 0)].get("name"),
        "summary": episode_summary.get("summary", ""),
        "cliffhanger": episode_summary.get("cliffhanger", ""),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video_file": episode_summary.get("video_file", ""),
    }
    state["episode_history"].append(record)

    # Set new cliffhanger for next episode
    state["last_cliffhanger"] = episode_summary.get("cliffhanger", "")

    # Advance episode number & day
    state["current_episode"] = ep_num + 1
    state["timeline_day"] = new_day

    # Check era progression
    eras = state.get("eras", [])
    cur_era_idx = state.get("current_era_index", 0)
    if cur_era_idx < len(eras):
        cur_era_dur = eras[cur_era_idx].get("duration_episodes", 15)
        # Calculate total episodes in eras up to this
        prior_dur = sum(eras[i].get("duration_episodes", 15) for i in range(cur_era_idx))
        if state["current_episode"] > (prior_dur + cur_era_dur) and cur_era_idx < len(eras) - 1:
            state["current_era_index"] = cur_era_idx + 1
            logger.info("Series '%s' has evolved to %s!", series_id, eras[state['current_era_index']].get('name'))

    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_series(series_id, state)
    return state


def list_all_series() -> List[Dict[str, Any]]:
    """Returns overview list of all existing series."""
    if not os.path.exists(SERIES_ROOT):
        return []
    items = []
    for name in os.listdir(SERIES_ROOT):
        s_dir = os.path.join(SERIES_ROOT, name)
        if os.path.isdir(s_dir):
            st = load_series(name)
            if st:
                items.append({
                    "series_id": st.get("series_id", name),
                    "title": st.get("title"),
                    "current_episode": st.get("current_episode", 1),
                    "timeline_day": st.get("timeline_day", 1),
                    "current_era": get_current_era(st).get("name"),
                    "episodes_produced": len(st.get("episode_history", [])),
                })
    return items
