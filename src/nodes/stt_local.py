"""Local STT fallback node: faster-whisper small.en int8 (spec 2.4).

Wired in when config/settings.yaml stt.provider == local_whisper. Building
the LiveKit custom-node wrapper is deliberately deferred: docs/FALLBACKS.md
prescribes asking before wiring local fallbacks early, and the launch tier
is the Deepgram plugin.
"""

from __future__ import annotations


def build_stt(model_name: str = "small.en"):
    raise NotImplementedError(
        "Local whisper node is the fallback tier and is not wired yet. "
        "Launch tier is the Deepgram plugin (config/settings.yaml). "
        "See docs/FALLBACKS.md before wiring this."
    )
