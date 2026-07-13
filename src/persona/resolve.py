"""Tags -> PersonaParams (spec 4.4). Function picks the base preset;
firm_type and seniority apply bounded adjustments: at most 0.10 on any
probe-mix weight and at most 0.2 on eagerness, enforced here regardless of
what any mapping table says. User overrides from the wizard's confirm step
apply last and are trusted.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.engine.state import PersonaParams
from src.persona.extract import PersonaTags

ROOT = Path(__file__).resolve().parents[2]
PERSONAS_DIR = ROOT / "config" / "personas"

MAX_WEIGHT_SHIFT = 0.10
MAX_EAGERNESS_SHIFT = 0.2

# Function -> base preset (spec 4.4 mapping table).
FUNCTION_PRESETS: dict[str, dict] = {
    "CONSULTING_PARTNER": {"preset_file": "consulting_partner.json"},
    "CONSUMER_PM": {"preset_file": "default_pm.json"},
    "TECHNICAL_PM": {
        "preset_file": "default_pm.json",
        "persona_id": "technical_pm",
        "display_name": "Technical PM interviewer",
        "probe_mix": {"specificity": 0.15, "ownership": 0.10, "quantify": 0.20,
                      "depth": 0.35, "counterfactual": 0.20},
        "interrupt_eagerness": 1.1,
        "topic_emphasis": ["execution", "tradeoffs"],
    },
    "PLATFORM_PM": {
        "preset_file": "default_pm.json",
        "persona_id": "platform_pm",
        "display_name": "Platform PM interviewer",
        "probe_mix": {"specificity": 0.20, "ownership": 0.10, "quantify": 0.20,
                      "depth": 0.30, "counterfactual": 0.20},
        "interrupt_eagerness": 1.0,
        "topic_emphasis": ["execution", "stakeholders"],
    },
    "ENG_LEADER": {
        "preset_file": "default_neutral.json",
        "persona_id": "eng_leader",
        "display_name": "Engineering leader",
        "round_profile": "tech",
        "probe_mix": {"specificity": 0.15, "ownership": 0.15, "quantify": 0.30,
                      "depth": 0.30, "counterfactual": 0.10},
        "interrupt_eagerness": 0.9,
        "topic_emphasis": ["tradeoffs", "execution"],
        "voice_preset": "clipped_fast",
    },
    "RECRUITER": {
        "preset_file": "default_neutral.json",
        "persona_id": "recruiter_screen",
        "display_name": "Recruiter screen",
        "probe_mix": {"specificity": 0.60, "ownership": 0.20, "quantify": 0.10,
                      "depth": 0.10},
        "interrupt_eagerness": 0.6,
        "interrupt_budget": 1,
        "intensity": 2,
        "opening_style": "warm",
        "voice_preset": "warm_slower",
    },
    "UNKNOWN": {"preset_file": "default_neutral.json"},
}

# Bounded style adjustments. Values here already respect the caps; the caps
# are still enforced after merging in case this table drifts.
FIRM_ADJUSTMENTS: dict[str, dict] = {
    "MBB": {"probe_mix": {"ownership": +0.05, "emotional": +0.05}, "interrupt_eagerness": +0.1},
    "BIG_TECH": {"probe_mix": {"quantify": +0.05}},
    "STARTUP": {"probe_mix": {"depth": +0.05}, "interrupt_eagerness": +0.1},
    "FINANCE": {"probe_mix": {"quantify": +0.05}, "interrupt_eagerness": +0.1},
    "OTHER": {},
    "UNKNOWN": {},
}

SENIORITY_ADJUSTMENTS: dict[str, dict] = {
    "PARTNER_DIRECTOR": {"interrupt_eagerness": +0.1, "intensity": +1},
    "SENIOR": {"interrupt_eagerness": +0.05},
    "MID": {},
    "UNKNOWN": {},
}

# Fixed voice library (spec 4.5): preset voices only, no cloning path.
# ElevenLabs voices referenced by stable voice_id (verified against the
# account's default library 2026-07-09); names are labels only.
# deepgram_voice maps each preset to the closest Deepgram Aura voice for
# the TTS fallback when ElevenLabs quota runs out. Groq Orpheus was tried
# first and rejected: autoregressive drift garbles longer utterances
# (verified against raw API output, 2026-07-12). All four models verified
# synthesizing 2026-07-12.
VOICE_LIBRARY: dict[str, dict] = {
    "measured_low": {"character": "measured-low", "elevenlabs_voice": "George",
                     "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb",
                     "deepgram_voice": "aura-2-apollo-en",
                     "kokoro_voice": "af_sarah", "speaking_rate": 0.95},
    "brisk_neutral": {"character": "brisk-neutral", "elevenlabs_voice": "Sarah",
                      "elevenlabs_voice_id": "EXAVITQu4vr4xnSDxMaL",
                      "deepgram_voice": "aura-2-thalia-en",
                      "kokoro_voice": "af_nicole", "speaking_rate": 1.0},
    "warm_slower": {"character": "warm-slower", "elevenlabs_voice": "Matilda",
                    "elevenlabs_voice_id": "XrExE9yKIg1WjnnlVkGX",
                    "deepgram_voice": "aura-2-helena-en",
                    "kokoro_voice": "af_bella", "speaking_rate": 0.9},
    "clipped_fast": {"character": "clipped-fast", "elevenlabs_voice": "Adam",
                     "elevenlabs_voice_id": "pNInz6obpgDQGcFmaJgB",
                     "deepgram_voice": "aura-2-arcas-en",
                     "kokoro_voice": "am_michael", "speaking_rate": 1.08},
}


def load_preset(name: str) -> dict:
    return json.loads((PERSONAS_DIR / name).read_text())


def _clamp_probe_mix(mix: dict[str, float], base: dict[str, float]) -> dict[str, float]:
    clamped = {}
    for probe_type, weight in mix.items():
        base_w = base.get(probe_type, 0.0)
        shift = max(-MAX_WEIGHT_SHIFT, min(MAX_WEIGHT_SHIFT, weight - base_w))
        clamped[probe_type] = max(0.0, base_w + shift)
    total = sum(clamped.values()) or 1.0
    return {k: v / total for k, v in clamped.items()}


def resolve(tags: PersonaTags, overrides: dict | None = None,
            selected_round: str | None = None) -> PersonaParams:
    spec = FUNCTION_PRESETS.get(tags.function, FUNCTION_PRESETS["UNKNOWN"])
    base = load_preset(spec["preset_file"])
    merged = {**base, **{k: v for k, v in spec.items() if k != "preset_file"}}

    base_mix = dict(merged["probe_mix"])
    base_eagerness = float(merged["interrupt_eagerness"])

    # Bounded adjustments from firm_type and seniority.
    mix = dict(base_mix)
    eagerness = base_eagerness
    intensity = int(merged["intensity"])
    for adj in (FIRM_ADJUSTMENTS.get(tags.firm_type, {}),
                SENIORITY_ADJUSTMENTS.get(tags.seniority, {})):
        for probe_type, delta in adj.get("probe_mix", {}).items():
            mix[probe_type] = mix.get(probe_type, 0.0) + delta
        eagerness += adj.get("interrupt_eagerness", 0.0)
        intensity += adj.get("intensity", 0)

    # Enforce bounds regardless of table contents.
    mix = _clamp_probe_mix(mix, base_mix)
    eagerness = max(base_eagerness - MAX_EAGERNESS_SHIFT,
                    min(base_eagerness + MAX_EAGERNESS_SHIFT, eagerness))
    merged["probe_mix"] = mix
    merged["interrupt_eagerness"] = round(eagerness, 3)
    merged["intensity"] = max(1, min(5, intensity))

    # domain_tags shift topic emphasis only (spec 4.2).
    if tags.domain_tags:
        emphasis = list(merged.get("topic_emphasis", []))
        merged["topic_emphasis"] = emphasis + [
            t for t in tags.domain_tags if t not in emphasis]

    # The user's selected round profile owns format rules; the persona does
    # not override that selection (spec 4.4 division of labor).
    if selected_round:
        merged["round_profile"] = selected_round

    # Wizard confirm-step overrides are trusted and win.
    for key, value in (overrides or {}).items():
        merged[key] = value

    rate = VOICE_LIBRARY.get(merged.get("voice_preset", ""), {}).get("speaking_rate")
    if rate and "speaking_rate" not in (overrides or {}):
        merged["speaking_rate"] = rate

    return PersonaParams(**merged)
