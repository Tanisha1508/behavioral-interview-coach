"""Persona resolution bounds and composition (items 3, 7)."""

from src.persona.extract import PersonaTags, Signal
from src.persona.resolve import (
    MAX_EAGERNESS_SHIFT,
    MAX_WEIGHT_SHIFT,
    load_preset,
    resolve,
)


def test_unknown_tags_fall_back_to_neutral():
    persona = resolve(PersonaTags(), selected_round="pm")
    assert persona.persona_id == "default_neutral"
    assert persona.round_profile == "pm"  # user's selection owns the round


def test_consulting_partner_maps_to_consulting_preset():
    tags = PersonaTags(function="CONSULTING_PARTNER", firm_type="MBB",
                       seniority="PARTNER_DIRECTOR")
    persona = resolve(tags, selected_round="consulting")
    assert persona.persona_id == "consulting_partner"
    assert persona.round_profile == "consulting"
    assert persona.interrupt_budget == 3
    # Emotional and ownership heavy per spec 4.4.
    assert persona.probe_mix.get("emotional", 0) > 0.2
    assert persona.probe_mix.get("ownership", 0) > 0.2


def test_adjustments_are_bounded():
    base = load_preset("consulting_partner.json")
    tags = PersonaTags(function="CONSULTING_PARTNER", firm_type="MBB",
                       seniority="PARTNER_DIRECTOR")
    persona = resolve(tags, selected_round="consulting")

    assert abs(persona.interrupt_eagerness - base["interrupt_eagerness"]) \
        <= MAX_EAGERNESS_SHIFT + 1e-9

    total = sum(persona.probe_mix.values())
    assert abs(total - 1.0) < 1e-6
    # Pre-normalization shifts are capped; after normalization each weight
    # stays within the cap plus normalization drift.
    for probe_type, base_weight in base["probe_mix"].items():
        assert abs(persona.probe_mix.get(probe_type, 0.0) - base_weight) \
            <= MAX_WEIGHT_SHIFT + 0.05


def test_recruiter_preset_values():
    persona = resolve(PersonaTags(function="RECRUITER"), selected_round="pm")
    assert persona.interrupt_budget == 1
    assert persona.intensity == 2
    assert persona.interrupt_eagerness <= 0.7
    assert "counterfactual" not in persona.probe_mix


def test_domain_tags_shift_topics_not_intensity():
    tags = PersonaTags(function="CONSUMER_PM", domain_tags=["voice", "growth"])
    with_tags = resolve(tags, selected_round="pm")
    without = resolve(PersonaTags(function="CONSUMER_PM"), selected_round="pm")
    assert "voice" in with_tags.topic_emphasis
    assert with_tags.intensity == without.intensity
    assert with_tags.interrupt_eagerness == without.interrupt_eagerness


def test_overrides_win():
    persona = resolve(PersonaTags(), overrides={"intensity": 5},
                      selected_round="pm")
    assert persona.intensity == 5


def test_round_profile_owns_format_persona_owns_style():
    """Composition (spec 4.4): persona carries style fields, and the round
    selection is never overridden by the persona preset."""
    tags = PersonaTags(function="CONSULTING_PARTNER")
    persona = resolve(tags, selected_round="pm")  # user picked pm anyway
    assert persona.round_profile == "pm"
    assert persona.intensity == 4  # style preserved from preset


def test_voice_library_presets_are_complete():
    """Every preset must carry both a verified ElevenLabs voice_id and a
    Deepgram Aura fallback voice (TTS FallbackAdapter, added 2026-07-12
    after the ElevenLabs quota ran out mid-session; Groq Orpheus was
    rejected for garbling long utterances)."""
    from src.persona.resolve import VOICE_LIBRARY
    for name, preset in VOICE_LIBRARY.items():
        assert preset["elevenlabs_voice_id"], name
        assert preset["deepgram_voice"].startswith("aura-2-"), name
        assert preset["speaking_rate"] > 0, name
