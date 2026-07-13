"""Local TTS fallback node: Kokoro-82M (spec 2.4).

Wired in when config/settings.yaml tts.provider == local_kokoro. Same
deferral rule as stt_local.py: launch tier is the ElevenLabs plugin, and
docs/FALLBACKS.md prescribes asking before switching early.
"""

from __future__ import annotations


def build_tts(voice: str = "af_nicole"):
    raise NotImplementedError(
        "Local Kokoro node is the fallback tier and is not wired yet. "
        "Launch tier is the ElevenLabs plugin (config/settings.yaml). "
        "See docs/FALLBACKS.md before wiring this."
    )
