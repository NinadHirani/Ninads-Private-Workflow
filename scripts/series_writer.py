#!/usr/bin/env python3
"""
Series Writer - AI Shorts Factory
Generates continuous episodic scripts and photorealistic scene prompts
with character visual anchors, era-specific worldbuilding, and cliffhanger chaining.
"""

import os
import sys
import json
import re
import random
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

logger = logging.getLogger("series_writer")
try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text: str) -> str:
            return text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_episodic_prompt(ctx: Dict[str, Any], target_duration: int = 40) -> str:
    """Builds a strict structured prompt for multi-tier LLMs."""
    return f"""You are a master cinematic screenwriter and gritty docu-fiction narrator producing an ongoing viral episodic series.

[SERIES CONTINUITY CONTEXT]
- Series: {ctx.get('series_title')}
- Episode: #{ctx.get('episode_number')} | In-Universe Timeline: Day {ctx.get('timeline_day')}
- Era: {ctx.get('era_name')} ({ctx.get('era_subtitle')})
- Era Lore: {ctx.get('era_description')}
- Current Location: {ctx.get('location')}
- Weather & Environment: {ctx.get('weather')}
- Primary Danger/Threat: {ctx.get('threat')}

[RECURRING PROTAGONIST]
- Name: {ctx.get('character_name')}
- Appearance Anchor: {ctx.get('character_identity')}
- Current Gear: {ctx.get('character_gear')}
- Physical Condition / Wounds: {ctx.get('character_wounds')}
- Mental State: {ctx.get('character_mindset')}

[PREVIOUS EPISODE CLIFFHANGER TO RESOLVE]
{ctx.get('last_cliffhanger')}

[RECENT STORY RECAP]
{ctx.get('recent_history_recap')}

[REQUIREMENTS]
1. NARRATION STYLE: Gritty, tense, third-person epic narrator documenting {ctx.get('character_name')}'s desperate survival and tactical choices.
2. CONTINUITY MANDATE: Line 1 of the narration MUST immediately acknowledge and resolve or react to the previous cliffhanger.
3. MIDDLE: Detail today's survival challenge, a critical moral or tactical decision, or an ominous discovery about this Era's lore.
4. CLIFFHANGER ENDING: The final narration line MUST end on a breathtaking cliffhanger that demands watching the next part.
5. PACING: Exactly 6 to 8 punchy spoken sentences (around 70 to 95 words total, suitable for ~{target_duration}s).
6. SCENE VISUAL PROMPTS: Generate exactly 4 visual prompts for vertical 9:16 AI image generation. Each prompt MUST embed {ctx.get('character_name')}'s visual identity:
   "Cinematic 35mm film still, vertical 9:16, ultra-realistic, dramatic lighting, {ctx.get('visual_palette')}. Featuring {ctx.get('character_name')}: {ctx.get('character_identity')}, [specific scene action, camera angle, and environment]".

OUTPUT FORMAT: Return ONLY a valid JSON object with the following schema:
{{
  "title": "Short punchy episode title (e.g., 'The Chittering in the Vents')",
  "script_lines": [
    "Sentence 1 (resolving last cliffhanger)",
    "Sentence 2...",
    "Sentence 3...",
    "Sentence 4...",
    "Sentence 5...",
    "Sentence 6...",
    "Final Sentence (shocking cliffhanger for next part)"
  ],
  "summary": "1-2 sentence overview of what occurred today",
  "cliffhanger": "Concise 1-sentence description of the final cliffhanger moment",
  "scene_prompts": [
    "Scene 1 visual prompt...",
    "Scene 2 visual prompt...",
    "Scene 3 visual prompt...",
    "Scene 4 visual prompt..."
  ],
  "days_passed": 1,
  "new_location": "optional new location if moved, or null",
  "new_wounds": "optional updated physical condition, or null",
  "new_gear": "optional updated inventory, or null"
}}
"""


def _clean_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts JSON dictionary from LLM response."""
    if not raw_text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", raw_text.strip(), flags=re.M).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "script_lines" in data:
            return data
    except Exception:
        pass

    # Regex extraction of JSON block
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "script_lines" in data:
                return data
        except Exception:
            pass
    return None


def _try_gemini_series(prompt: str) -> Optional[Dict[str, Any]]:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    text = out["candidates"][0]["content"]["parts"][0]["text"]
    return _clean_json_response(text)


def _try_groq_series(prompt: str) -> Optional[Dict[str, Any]]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.75,
        "response_format": {"type": "json_object"}
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    text = out["choices"][0]["message"]["content"]
    return _clean_json_response(text)


def _try_pollinations_series(prompt: str) -> Optional[Dict[str, Any]]:
    if os.getenv("SHORTS_MOCK") == "1":
        return None
    try:
        url = "https://text.pollinations.ai/"
        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "model": "openai",
            "jsonMode": True
        }).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "AI-Shorts-Factory/Series-1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        return _clean_json_response(text)
    except Exception as exc:
        logger.debug("Pollinations series text unavailable: %s", redact(str(exc)))
        return None


def generate_procedural_series_episode(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent combinatorial procedural episode generator.
    Guarantees 100% offline uptime and rigorous continuity without external API dependencies.
    """
    ep = ctx.get("episode_number", 1)
    day = ctx.get("timeline_day", 1)
    name = ctx.get("character_name", "Kane")
    era = ctx.get("era_name", "The Ash Fall")
    palette = ctx.get("visual_palette", "cinematic photorealistic gritty")
    identity = ctx.get("character_identity", "weathered survivor in tactical coat")
    cliff = ctx.get("last_cliffhanger", "")
    loc = ctx.get("location", "Sector 4 ruins")

    resolutions = [
        f"When the shadow lunged from the dark, {name} didn't flinch—he rolled beneath the rusted beams as talons tore through the concrete.",
        f"The echoing growl in the corridor faded just inches from {name}'s position, leaving only the sound of ash dripping through the iron grate.",
        f"{name} held his breath behind the blast door as heavy footsteps dragged across the steel plates above him.",
        f"The emergency flares flickered out, plunging the tunnel into pitch darkness, but {name}'s hand was already on his blade.",
    ]
    res_line = random.choice(resolutions) if cliff and "None" not in cliff else f"Day {day} began with the bitter taste of sulfur and silence across {loc}."

    mid_arcs = [
        [
            f"The air scrubbers in this sector died decades ago, forcing {name} to ration his remaining oxygen canister.",
            f"Scavenging through the overturned convoy yielded a military data drive, still faintly pulsing with encrypted power.",
            f"Every step through the ash revealed fresh claw marks gouged six inches deep into reinforced rebar.",
            f"Survival in {era} isn't about fighting every beast—it is about knowing when to become invisible.",
        ],
        [
            f"A strange electromagnetic frequency hummed through {name}'s Geiger counter, pointing toward the collapsed subway line.",
            f"Water was running low, but the pools below were black and shimmering with toxic bioluminescence.",
            f"He rigged an acoustic tripwire across the stairwell, buying himself twenty minutes to inspect the scavenged radio.",
            f"The static whispered a coordinates signal, repeating a voice transmission long thought extinct.",
        ],
        [
            f"{name}'s bandaged shoulder throbbed with every heavy breath, a constant reminder of how thin the line is between hunter and prey.",
            f"Deep in the vault, he uncovered an intact pressurized seal that hasn't seen sunlight since the first bombs fell.",
            f"A distant seismic tremor shook dust from the ceiling, dislodging old structural beams into the flooded trench.",
            f"He tightened his pack straps and stepped into the breach, knowing turning back meant certain starvation.",
        ]
    ]
    mid_lines = random.choice(mid_arcs)

    cliffhangers = [
        f"Then the signal receiver beeped twice, and a voice from the static spoke his name.",
        f"A massive seismic tremor cracked the vault floor in two, exposing an obsidian structure humming with purple light.",
        f"From the pitch black rafters above, two crimson optic sensors ignited directly over his head.",
        f"The reinforced steel door slammed shut behind him with an automated hydraulic hiss, locking him inside.",
        f"He aimed his flashlight down the shaft—and saw hundreds of eyes staring back from the dark.",
    ]
    cliff_line = random.choice(cliffhangers)

    lines = [res_line] + mid_lines + [cliff_line]
    title = f"Day {day}: {random.choice(['The Breach', 'Echoes in the Ash', 'The Silent Vault', 'Dead Air', 'The Chittering'])}"

    prompts = [
        f"Cinematic 35mm film still, vertical 9:16, photorealistic, {palette}. Featuring {name}: {identity}, tense survival reaction shot, dramatic volumetric shadows, Kodak film grain",
        f"Cinematic 35mm film still, vertical 9:16, photorealistic, {palette}. Featuring {name}: {identity}, cautiously scavenging through {loc}, dust particles caught in narrow flashlight beam, 8k realism",
        f"Cinematic 35mm film still, vertical 9:16, photorealistic, {palette}. Featuring {name}: {identity}, close up of weathered hands holding signature survival gear, dramatic cinematic lighting, hyper-detailed texture",
        f"Cinematic 35mm film still, vertical 9:16, photorealistic, {palette}. Featuring {name}: {identity}, dramatic confrontation cliffhanger shot, silhouette against ominous glowing atmospheric anomaly, wide angle vertical",
    ]

    return {
        "title": title,
        "script_lines": lines,
        "summary": f"{name} pushed through {loc} under {era}, encountering anomalous signals and facing unexpected danger.",
        "cliffhanger": cliff_line,
        "scene_prompts": prompts,
        "days_passed": random.choice([1, 2]),
        "new_location": loc,
        "new_wounds": None,
        "new_gear": None,
    }


def write_series_episode(ctx: Dict[str, Any], target_duration: int = 40) -> Dict[str, Any]:
    """
    Writes the next episodic installment using the multi-tier LLM chain,
    falling back to procedural generation seamlessly.
    """
    prompt = build_episodic_prompt(ctx, target_duration=target_duration)

    generators = [
        ("gemini", _try_gemini_series),
        ("groq", _try_groq_series),
    ]
    if os.getenv("USE_POLLINATIONS_TEXT", "1") == "1" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")):
        generators.append(("pollinations", _try_pollinations_series))

    for gen_name, fn in generators:
        try:
            res = fn(prompt)
            if res and isinstance(res.get("script_lines"), list) and len(res["script_lines"]) >= 4:
                logger.info("Successfully generated episode #%s via %s", ctx.get("episode_number"), gen_name)
                # Ensure 4 scene prompts exist
                if not res.get("scene_prompts") or len(res["scene_prompts"]) < 4:
                    res["scene_prompts"] = [
                        f"Cinematic 35mm film still, vertical 9:16, photorealistic, {ctx.get('visual_palette')}. Featuring {ctx.get('character_name')}: {ctx.get('character_identity')}, surviving in {ctx.get('location')}"
                        for _ in range(4)
                    ]
                res["writer"] = gen_name
                return res
        except Exception as exc:
            logger.warning("Episode generation failed via %s: %s", gen_name, redact(str(exc)))

    # Fallback to procedural generator
    logger.info("Using procedural continuity story engine for episode #%s", ctx.get("episode_number"))
    proc = generate_procedural_series_episode(ctx)
    proc["writer"] = "procedural_continuity_engine"
    return proc
