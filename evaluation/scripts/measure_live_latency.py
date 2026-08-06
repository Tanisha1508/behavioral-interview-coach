"""NOT RUN as part of this evaluation -- this is a reproduction stub for the
one metric this evaluation could not measure from a batch script: true
end-to-end, voice-to-voice interview latency (time from the candidate
finishing speaking to the interviewer's audio starting) and its TTFT-
equivalent for a live session.

Why it can't be done in a batch script: src/agent.py's DrillRunner only
becomes reachable inside a live LiveKit AgentSession, driven by a real
(or piped) audio track. There is no headless "call the runner with an audio
file" path in this codebase today -- session.say() and STT partials are
wired to a live room.

How to actually run this:
  1. `python -m src.agent console` (console mode; needs a real microphone,
     or route a pre-recorded WAV into the input device with a virtual audio
     cable / loopback, e.g. BlackHole on macOS or a PulseAudio null sink on
     Linux).
  2. Patch DrillRunner.say (src/agent.py) to record a timestamp the instant
     it's called, and separately hook `session.on("user_input_transcribed")`
     (already wired at src/agent.py's `_on_transcribed`) to record the
     timestamp of the final transcript that triggered `on_turn_complete`.
  3. end_to_end_latency_s = timestamp(say call after grading) -
     timestamp(final transcript that ended the answer). This captures
     STT-finalize + grade() + say()-dispatch, which is the real user-felt
     latency between "I'm done talking" and "the interviewer responds."
  4. For a TTFT-equivalent: LiveKit's TTS plugins emit an "on first audio
     frame" event internally; the livekit-agents metrics API
     (agents.metrics, see the installed livekit-agents package) exposes
     TTFB-style events per TTS/STT/LLM call in newer versions -- check
     `python -c "import livekit.agents.metrics as m; print(dir(m))"`
     against the pinned 1.6.4 version before relying on it, since the
     product's own DECISIONS.md notes this exact version was pinned after
     a cloud image drift incident (2026-07-13) and metrics APIs have
     changed across livekit-agents versions.

This file intentionally contains no fabricated numbers. Fill in the
measurement loop above and re-run against a live session to get real ones.
"""

raise SystemExit(
    "This is a reproduction stub, not a runnable eval. See the module "
    "docstring for what a live measurement requires (a live LiveKit "
    "AgentSession + real or piped audio) and how to wire it."
)
