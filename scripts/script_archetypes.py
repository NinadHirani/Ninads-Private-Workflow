#!/usr/bin/env python3
"""
Script Archetypes & Story Matrix - AI Shorts Factory
Defines dynamic storytelling archetypes, emotional tones, language handling,
duration-scaled pacing, and combinatorial sentence banks for offline fallback.
"""
import os
import re
import json
import random
import logging

try:
    from scripts.log_sanitizer import redact
except ImportError:
    try:
        from log_sanitizer import redact
    except ImportError:
        def redact(text):
            return text

logger = logging.getLogger("script_archetypes")

# Words per second for typical spoken commentary (Edge-TTS)
WORDS_PER_SECOND = 2.4

# Supported Archetypes
ARCHETYPES = {
    "narrative_story": {
        "name": "Micro-Documentary / Story Arc",
        "description": "Character or event-driven arc: Setup -> Turning Point -> Climax -> Takeaway",
        "structure": [
            "Hook introducing the central figure or pivotal moment",
            "Inciting incident or unexpected conflict",
            "Rising tension or turning point where the stakes change",
            "The climactic revelation or surprising resolution",
            "Punchy takeaway connecting to modern reality"
        ]
    },
    "paradox_mystery": {
        "name": "Curiosity Paradox / Myth-Buster",
        "description": "Contradiction that shatters common sense: Mystery -> Evidence -> Revelation",
        "structure": [
            "Irresistible contradiction or paradox that stops the scroll",
            "The common assumption that everyone blindly believes",
            "The hidden data or clue that breaks the illusion",
            "The chilling or awe-inspiring truth behind reality",
            "Mind-bending final thought that loops back"
        ]
    },
    "provocative_debate": {
        "name": "Hot Take / Provocative Debate",
        "description": "Polarizing, contrarian take: Uncomfortable Truth -> Deconstruction -> Challenge",
        "structure": [
            "Bold controversial claim that sparks immediate reaction",
            "Why the standard mainstream opinion is completely flawed",
            "The undeniable proof or mechanism backing the hot take",
            "What this implies for anyone who ignores it",
            "Direct challenge to the viewer triggering comment debate"
        ]
    },
    "breakdown_mechanics": {
        "name": "Fast Blueprint / Secret Mechanics",
        "description": "Rapid, high-retention breakdown: Secret Trick -> How It Works -> Mind Shift",
        "structure": [
            "Shocking hook about a secret, cheat-code, or hidden system",
            "The single fatal mistake most people make",
            "The exact breakdown of how the mechanism operates step by step",
            "The unfair advantage gained by knowing this",
            "Memorable action prompt or viral loop"
        ]
    },
    "deep_reflection": {
        "name": "Philosophical / Atmospheric Reflection",
        "description": "Stoic, cosmic, or deep wisdom: Perspective Shift -> Timeless Truth -> Resonant Loop",
        "structure": [
            "Profound observation cutting through modern daily noise",
            "Ancient or psychological reality we constantly ignore",
            "The painful cost of continuing the current path",
            "The shift in perspective that brings unshakeable mastery",
            "Final resonant statement echoing back to line one"
        ]
    },
    "emotional_journey": {
        "name": "Visceral Struggle & Triumph",
        "description": "Raw human or character struggle: Adversity -> Breaking Point -> Triumph",
        "structure": [
            "Heart-wrenching or intense moment of defeat or rock bottom",
            "The moment everyone thought it was completely over",
            "The quiet decision to endure and fight back against all odds",
            "The explosive turning point that rewrote destiny",
            "Inspirational takeaway that gives chills"
        ]
    },
    "indian_brainrot": {
        "name": "Desi Brainrot / Viral Indian Commentary",
        "description": "High-octane, spicy Hindi/Hinglish commentary with relatable desi humor and shock value",
        "structure": [
            "Explosive conversational hook (e.g. 'Bhai ye dekh ke tumhara dimaag hil jayega')",
            "Shocking claim or reality that sounds like pure fiction",
            "Relatable desi comparison or hilarious mind-blowing breakdown",
            "The unbelievable twist that nobody saw coming",
            "Spicy call to action sparking madness in the comments"
        ]
    }
}

# Emotional Tones
EMOTIONAL_TONES = {
    "suspenseful_dark": {
        "vibe": "Chilling, eerie, mysterious, and breathless tension",
        "speed_rate": "-2%",
        "pitch": "-2Hz",
        "words_style": "unsettling, enigmatic, sharp, chilling"
    },
    "awe_inspiring": {
        "vibe": "Epic, cosmic, mind-expanding, and wondrous",
        "speed_rate": "-1%",
        "pitch": "+0Hz",
        "words_style": "vast, majestic, breathtaking, infinite"
    },
    "urgent_insider": {
        "vibe": "Fast-paced, confidential, high stakes, secret intelligence",
        "speed_rate": "+4%",
        "pitch": "+1Hz",
        "words_style": "crucial, classified, urgent, decisive"
    },
    "stoic_grounded": {
        "vibe": "Calm, deeply authoritative, rational, and unshakeable",
        "speed_rate": "-3%",
        "pitch": "-1Hz",
        "words_style": "discipline, clarity, truth, mastery"
    },
    "high_energy_hype": {
        "vibe": "Punchy, electrifying, rapid delivery with intense hype",
        "speed_rate": "+5%",
        "pitch": "+2Hz",
        "words_style": "insane, unstoppable, legendary, game-changing"
    },
    "desi_brainrot": {
        "vibe": "High-octane, spicy, hilarious, relatable Hinglish/Hindi street energy",
        "speed_rate": "+4%",
        "pitch": "+1Hz",
        "words_style": "bawaal, khatarnak, dimag ki batti, viral, scene set"
    }
}

# Offline Procedural Sentence Banks (combinatorial variation so offline scripts never repeat)
COMBINATORIAL_BANKS = {
    "narrative_story": {
        "hooks": [
            "In a single moment, the entire fate of {topic} hung by a thread.",
            "Nobody expected what was about to happen when {topic} was pushed to the absolute edge.",
            "This is the untold story of how {topic} completely defied the odds.",
            "History almost forgot the turning point that redefined {topic} forever.",
        ],
        "turnings": [
            "Just when defeat seemed certain, a radical choice broke every rule.",
            "Against impossible pressure, one instinct turned the battlefield upside down.",
            "What happened next was something even the experts could not predict.",
            "Instead of backing down, they doubled down on an impossible gamble.",
        ],
        "climaxes": [
            "The outcome shattered expectations and silenced every single skeptic.",
            "In seconds, what felt like guaranteed loss transformed into raw dominance.",
            "The ripples of that single second are still felt across the world today.",
            "It proved that real mastery isn't about avoiding chaos, it's about mastering it.",
        ],
        "loops": [
            "And that is why nobody will ever look at {topic} the same way again.",
            "Which side of this story would you stand on? Tell me below.",
            "Remember this next time you think the odds are stacked against you.",
        ]
    },
    "paradox_mystery": {
        "hooks": [
            "There is a chilling paradox hidden inside {topic} that science rarely explains.",
            "What if everything you were told about {topic} is an elaborate illusion?",
            "Look closely at {topic}, because the raw reality makes zero sense.",
            "The more you investigate {topic}, the more unsettling the answers become.",
        ],
        "turnings": [
            "On the surface, everything seems completely ordinary until you measure the anomalies.",
            "Every conventional theory breaks down the exact moment you inspect the core evidence.",
            "Researchers kept hitting an impossible wall whenever they tried to rationalize this.",
            "Behind closed doors, the data pointed to a conclusion nobody wanted to admit.",
        ],
        "climaxes": [
            "What they finally uncovered completely shatters our standard understanding.",
            "It turns out the glitch wasn't in our instruments, it was in reality itself.",
            "The deeper we go, the clearer it becomes that we are missing the biggest piece.",
            "This contradiction challenges the very laws we took for granted.",
        ],
        "loops": [
            "Do you think humanity is ready to face this truth? Let's debate.",
            "Save this, because this paradox will keep you up tonight.",
            "Are we observing the truth, or just what we were allowed to see?",
        ]
    },
    "provocative_debate": {
        "hooks": [
            "Most people are completely wrong about {topic}, and it's not even close.",
            "Here is the uncomfortable truth about {topic} that nobody wants to admit.",
            "Stop pretending that {topic} is working the way people claim.",
            "The mainstream opinion on {topic} is designed to keep you in the dark.",
        ],
        "turnings": [
            "Everyone follows the exact same formula without questioning who actually benefits.",
            "The loudest voices are defending an outdated system that is already crumbling.",
            "When you strip away the hype, the numbers tell an entirely different story.",
            "People get emotional because deep down, they know the old playbook is dead.",
        ],
        "climaxes": [
            "The ones who recognize this early are pulling ahead at lightspeed.",
            "The gap between those who adapt and those who complain is expanding daily.",
            "Reality doesn't care about comfort, it rewards those who face the truth.",
            "Once you see the pattern, you can never unsee it.",
        ],
        "loops": [
            "Do you agree, or are you still defending the old way? Tell me.",
            "Hit follow if you'd rather hear the raw truth than comfortable lies.",
            "Share this with someone who needs a reality check on {topic}.",
        ]
    },
    "breakdown_mechanics": {
        "hooks": [
            "Here is the secret mechanic behind {topic} that feels completely unfair.",
            "Once you understand how {topic} actually operates, everything changes.",
            "Top performers use this hidden rule of {topic} to stay untouchable.",
            "This single breakdown will save you years of trial and error with {topic}.",
        ],
        "turnings": [
            "Step one is throwing out the conventional advice that slows everybody else down.",
            "The core leverage comes from focusing entirely on the 20% that dictates 80% of results.",
            "Instead of forcing brute effort, you exploit the hidden friction point.",
            "Every master in this space optimizes for momentum rather than perfection.",
        ],
        "climaxes": [
            "This produces an exponential surge that compounds faster than anything else.",
            "While the crowd burns out, you bypass the bottleneck completely.",
            "That is the exact difference between struggling and effortless dominance.",
            "It looks like magic from the outside, but it's just pure leverage.",
        ],
        "loops": [
            "Try this today and see the results for yourself.",
            "Bookmark this before you lose it in your feed.",
            "Now you have the blueprint. What will you build with it?",
        ]
    },
    "deep_reflection": {
        "hooks": [
            "Take a deep breath and look at how {topic} mirrors the human mind.",
            "Most people spend their entire lives chasing peace, yet completely misunderstand {topic}.",
            "Marcus Aurelius and the ancient Stoics understood this truth about {topic} centuries ago.",
            "You cannot control the storm around you, but you can master your response to {topic}.",
        ],
        "turnings": [
            "We suffer not from events themselves, but from the judgment we attach to them.",
            "When you silence the noise, what remains is calm, unshakeable clarity.",
            "Everything outside your direct control is merely practice for your inner resilience.",
            "The mountain does not move because of the wind; it remains rooted and still.",
        ],
        "climaxes": [
            "True strength is not reacting to every wave, but being the anchor beneath them.",
            "When you master your focus, nothing outside can ever break your serenity.",
            "Discipline is not punishment; it is the ultimate form of self-respect.",
            "Peace is not something you discover; it is a fortress you build within.",
        ],
        "loops": [
            "Pause for ten seconds and let this truth sink into your day.",
            "Save this reminder for the next time life tries to test your peace.",
            "Master your mind, and you master your entire world.",
        ]
    },
    "indian_brainrot": {
        "hooks": [
            "Bhai ye sunkar tumhara dimaag hil jayega, {topic} ka sach suno!",
            "Agar tumhe lagta hai ki {topic} normal hai, toh yeh 20 second dhyan se dekho.",
            "Desi public, {topic} ke baare me yeh secret koi nahi batayega!",
            "Ruko ruko! {topic} ka yeh scene dekh ke scientists bhi shock me hain!",
        ],
        "turnings": [
            "Pehle sabko lagta tha ki yeh bas ek aam cheez hai, par jab sach samne aaya toh sab dhang reh gaye.",
            "Kyunki background me jo chal raha tha, wo kisi movie se kam nahi tha.",
            "Iska formula itna khatarnak hai ki ordinary log isko samajh hi nahi paate.",
            "Log baatein karte reh gaye, aur idhar scene hi palat gaya!",
        ],
        "climaxes": [
            "Bhai level hi alag hai! Isne poorane saare records dhoo-dhaa ke khatam kar diye.",
            "Ab samajh aaya ki log iske piche itne deewane kyun hain!",
            "Yeh dekhne ke baad koi bhi bol dega ki bhai, yeh toh agle level ka dimag hai.",
            "Matlab asambhav ko sambhav kar dikhaya bina kisi drama ke!",
        ],
        "loops": [
            "Tumhara kya kehna hai bhai ispe? Jaldi comments me batao!",
            "Agar dimaag ki batti jal gayi ho, toh subscribe button tod do!",
            "Dosto ke sath share karo aur unka bhi dimaag hila do!",
        ]
    }
}

# Hindi / Hinglish keyword indicators for auto-detection
HINDI_INDICATORS = [
    "bhai", "kya", "kyun", "kaise", "raaz", "dimaag", "sach", "khatarnak", "bawaal",
    "desh", "desi", "dost", "jugaad", "chal", "ruko", "dekho", "shandar", "pagal",
    "bharat", "india", "bollywood", "hindi", "hinglish", "scene", "shuru", "karo"
]


def detect_language(topic: str) -> str:
    """Detects whether topic has Hindi / Hinglish context or is standard English."""
    t = (topic or "").lower()
    # Check for Devanagari Unicode range (0900-097F)
    if any("\u0900" <= ch <= "\u097f" for ch in t):
        return "hindi"

    tokens = set(re.findall(r"[a-z]+", t))
    if any(k in tokens for k in HINDI_INDICATORS):
        return "hinglish"

    return "english"


def auto_select_matrix(topic: str, category: str = None) -> dict:
    """Intelligently detects archetype, emotional tone, and language based on topic & genre."""
    t = (topic or "").lower()
    lang = detect_language(topic)

    # 1. Indian / Desi Brainrot priority if language is Hindi/Hinglish or Indian context
    if lang in ("hindi", "hinglish") or any(k in t for k in ("desi", "bollywood", "jugaad", "india")):
        return {
            "archetype": "indian_brainrot",
            "emotion": "desi_brainrot",
            "language": lang if lang != "english" else "hinglish"
        }

    # 2. Stoic & Philosophy
    if category == "stoic" or any(w in t for w in ("stoic", "marcus", "seneca", "philosophy", "mindset", "peace", "discipline")):
        return {
            "archetype": "deep_reflection",
            "emotion": "stoic_grounded",
            "language": "english"
        }

    # 3. Facts & Mystery & Sci-Fi Lore
    if category in ("facts_mystery", "scifi_lore") or any(w in t for w in ("paradox", "mystery", "space", "dark", "secret", "quantum", "alien", "glitch", "truth")):
        return {
            "archetype": "paradox_mystery",
            "emotion": "suspenseful_dark",
            "language": "english"
        }

    # 4. Tech & AI & Future
    if category == "tech_ai" or any(w in t for w in ("ai", "robot", "tech", "breakthrough", "coding", "future", "algorithm", "agi")):
        chosen_arch = random.choice(["breakdown_mechanics", "provocative_debate"])
        return {
            "archetype": chosen_arch,
            "emotion": "urgent_insider",
            "language": "english"
        }

    # 5. Anime & Movie Storylines
    if category in ("anime", "movie", "gaming") or any(w in t for w in ("anime", "movie", "fight", "game", "goku", "saitama", "boss", "hero")):
        return {
            "archetype": "narrative_story",
            "emotion": "high_energy_hype",
            "language": "english"
        }

    # 6. Default balanced rotation with diverse variety
    options = [
        {"archetype": "narrative_story", "emotion": "awe_inspiring"},
        {"archetype": "breakdown_mechanics", "emotion": "urgent_insider"},
        {"archetype": "provocative_debate", "emotion": "high_energy_hype"},
        {"archetype": "deep_reflection", "emotion": "stoic_grounded"},
        {"archetype": "paradox_mystery", "emotion": "suspenseful_dark"}
    ]
    picked = random.choice(options)
    picked["language"] = "english"
    return picked


def calculate_pacing_targets(duration_seconds: int = 45) -> dict:
    """Calculates ideal word count, sentence count range, and line length for the target duration."""
    sec = max(10, min(int(duration_seconds or 45), 65))
    target_words = int(sec * WORDS_PER_SECOND)

    if sec <= 20:
        min_lines, max_lines = 3, 5
        target_words = min(target_words, 45)
    elif sec <= 35:
        min_lines, max_lines = 5, 7
        target_words = min(target_words, 80)
    elif sec <= 48:
        min_lines, max_lines = 6, 9
        target_words = min(target_words, 115)
    else:
        min_lines, max_lines = 8, 12
        target_words = min(target_words, 145)

    return {
        "duration_seconds": sec,
        "target_words": target_words,
        "min_lines": min_lines,
        "max_lines": max_lines
    }


def load_external_prompt_override(archetype: str) -> str:
    """Checks prompts/ directory or prompts/archetypes/ for custom user prompt templates."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(root, "prompts", "archetypes", f"{archetype}.txt"),
        os.path.join(root, "prompts", f"{archetype}_prompt.txt"),
        os.path.join(root, "prompts", "custom_script.txt"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    logger.info("Loaded custom prompt template from %s", path)
                    return content
            except Exception as e:
                logger.warning("Could not read prompt override %s: %s", path, redact(str(e)))
    return None


def build_system_prompt(topic: str, archetype_key: str, emotion_key: str, duration: int = 45, language: str = "english") -> str:
    """Constructs a comprehensive, dynamic prompt combining Archetype, Emotion, Duration, and Language."""
    override = load_external_prompt_override(archetype_key)
    if override:
        return override.format(
            topic=topic,
            duration=duration,
            archetype=archetype_key,
            emotion=emotion_key,
            language=language
        )

    arch = ARCHETYPES.get(archetype_key, ARCHETYPES["narrative_story"])
    emotion = EMOTIONAL_TONES.get(emotion_key, EMOTIONAL_TONES["awe_inspiring"])
    pacing = calculate_pacing_targets(duration)

    struct_bullets = "\n".join(f"- {s}" for s in arch["structure"])

    lang_instruction = "Natural, conversational spoken English."
    if language == "hindi":
        lang_instruction = "Spoken Hindi (Devanagari script or conversational standard Hindi). Energetic and engaging."
    elif language == "hinglish":
        lang_instruction = "Conversational Hinglish (Hindi written in English alphabet with popular English words). Highly viral, relatable, and spicy."

    prompt = f"""You are a master viral storyteller crafting a high-retention vertical video script (YouTube Shorts & Instagram Reels).

Topic: {topic}
Storytelling Archetype: {arch['name']} ({arch['description']})
Emotional Tone & Vibe: {emotion['vibe']} ({emotion['words_style']})
Target Spoken Duration: ~{pacing['duration_seconds']} seconds ({pacing['target_words']} total spoken words).
Sentence Constraints: Between {pacing['min_lines']} and {pacing['max_lines']} fluid spoken sentences.
Language: {lang_instruction}

Story Arc Structure:
{struct_bullets}

Strict Guidelines:
1. Every sentence must flow naturally into the next with gripping narrative propulsion.
2. NO stage directions, NO narrator labels, NO bullet numbers, NO emojis.
3. Keep spoken words punchy and rhythmic, crafted for text-to-speech voiceover.
4. Final sentence must leave a lingering impression, provoke debate, or loop back.

You MUST respond with ONLY a valid JSON array of strings, where each element is one spoken sentence.
Example format:
["Sentence one here.", "Sentence two here.", "Sentence three here."]
"""
    return prompt.strip()


def generate_combinatorial_script(topic: str, archetype: str, duration: int = 45, language: str = "english") -> list:
    """Procedurally generates a varied, non-repetitive script offline using combinatoric sentence banks."""
    title_topic = " ".join(w.capitalize() for w in topic.split())

    if language in ("hindi", "hinglish") or archetype == "indian_brainrot":
        bank = COMBINATORIAL_BANKS["indian_brainrot"]
    else:
        bank = COMBINATORIAL_BANKS.get(archetype, COMBINATORIAL_BANKS["narrative_story"])

    pacing = calculate_pacing_targets(duration)
    needed_lines = random.randint(pacing["min_lines"], pacing["max_lines"])

    hook = random.choice(bank["hooks"]).format(topic=title_topic)
    turn1 = random.choice(bank["turnings"]).format(topic=title_topic)
    climax = random.choice(bank["climaxes"]).format(topic=title_topic)
    loop = random.choice(bank["loops"]).format(topic=title_topic)

    lines = [hook, turn1]

    # Add extra middle variations if target duration requires more lines
    if needed_lines >= 5:
        alt_turns = [t for t in bank["turnings"] if t != turn1]
        if alt_turns:
            lines.append(random.choice(alt_turns).format(topic=title_topic))

    lines.append(climax)

    if needed_lines >= 6:
        alt_climaxes = [c for c in bank["climaxes"] if c != climax]
        if alt_climaxes:
            lines.append(random.choice(alt_climaxes).format(topic=title_topic))

    lines.append(loop)
    return lines
