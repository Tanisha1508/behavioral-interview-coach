'use client';

import { useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import {
  useMaybeRoomContext,
  useMultibandTrackVolume,
  useVoiceAssistant,
} from '@livekit/components-react';

// The session agent tile: the owl mascot that listens, thinks, and speaks.
// It reads the agent's voice-assistant state and audio track directly, so it
// works anywhere inside the room context. Beak, mouth, halo, and head-bob are
// driven by the live audio amplitude (--amp); breathe/tilt/blink come from the
// state via data-state. All styling lives in styles/globals.css (.owl-*).

const VISUAL_STATE: Record<string, 'listening' | 'thinking' | 'speaking'> = {
  listening: 'listening',
  thinking: 'thinking',
  speaking: 'speaking',
  connecting: 'thinking',
  initializing: 'thinking',
  disconnected: 'listening',
};

const CAPTION: Record<string, string> = {
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  connecting: 'Connecting',
  initializing: 'Warming up',
  disconnected: 'Listening',
};

export function SpeakingOwl() {
  const { state, audioTrack } = useVoiceAssistant();
  const bands = useMultibandTrackVolume(audioTrack, { bands: 5, loPass: 100, hiPass: 200 });
  const room = useMaybeRoomContext();

  // Scoring runs in a background thread the LiveKit voice-assistant state
  // cannot see, so the agent sends an explicit "agent_phase" thinking signal
  // (set while grading, cleared after). Honor it here.
  const [thinkingPhase, setThinkingPhase] = useState(false);
  useEffect(() => {
    if (!room) return;
    const decoder = new TextDecoder();
    const onData = (payload: Uint8Array, _p?: unknown, _k?: unknown, topic?: string) => {
      if (topic !== 'agent_phase') return;
      try {
        setThinkingPhase(JSON.parse(decoder.decode(payload)).phase === 'thinking');
      } catch {
        // ignore malformed phase messages
      }
    };
    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room]);

  const base = VISUAL_STATE[state] ?? 'listening';
  // Speaking always wins; otherwise a thinking signal overrides idle/listening.
  const visual = thinkingPhase && base !== 'speaking' ? 'thinking' : base;
  const raw = bands.length ? bands.reduce((a, b) => a + b, 0) / bands.length : 0;
  // Only the speaking state should move the beak/halo; other states hold at 0
  // even if the track carries a little residual noise.
  const amp = visual === 'speaking' ? Math.min(1, raw * 1.6) : 0;
  const label = visual === 'thinking' ? 'Thinking' : (CAPTION[state] ?? 'Listening');

  return (
    <div className="owl-stage" data-state={visual} style={{ '--amp': amp } as React.CSSProperties}>
      <div className="owl-area">
        <div className="owl-glow" />
        <div className="owl-halo r1" />
        <div className="owl-halo r2" />
        <div className="owl-halo r3" />
        <div className="owl-wrap">
          <svg viewBox="0 0 120 120" fill="none" role="img" aria-label="Interview coach owl">
            {/* ear tufts */}
            <path d="M30 30 L38 12 L48 26 Z" fill="var(--primary)" />
            <path d="M90 30 L82 12 L72 26 Z" fill="var(--primary)" />
            {/* body */}
            <ellipse cx="60" cy="66" rx="42" ry="46" fill="var(--primary)" />
            {/* wings */}
            <path
              d="M20 60 q-6 22 12 34 q-2-18 0-30 Z"
              fill="color-mix(in oklab, var(--primary) 78%, black)"
            />
            <path
              d="M100 60 q6 22 -12 34 q2-18 0-30 Z"
              fill="color-mix(in oklab, var(--primary) 78%, black)"
            />
            {/* belly */}
            <ellipse cx="60" cy="80" rx="26" ry="27" fill="var(--card)" />
            {/* belly feather rows */}
            <path
              d="M44 74 q4 5 8 0 q4 5 8 0 q4 5 8 0 q4 5 8 0 M48 86 q4 5 8 0 q4 5 8 0 q4 5 8 0"
              stroke="color-mix(in oklab, var(--primary) 30%, transparent)"
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
            />
            {/* face discs */}
            <circle cx="42" cy="46" r="17" fill="var(--card)" />
            <circle cx="78" cy="46" r="17" fill="var(--card)" />
            {/* glasses */}
            <circle
              cx="42"
              cy="46"
              r="13.5"
              stroke="var(--foreground)"
              strokeWidth="3"
              fill="none"
            />
            <circle
              cx="78"
              cy="46"
              r="13.5"
              stroke="var(--foreground)"
              strokeWidth="3"
              fill="none"
            />
            <path
              d="M55.5 46 h9"
              stroke="var(--foreground)"
              strokeWidth="3"
              strokeLinecap="round"
            />
            {/* eyes (blink) */}
            <g className="owl-eye">
              <circle cx="42" cy="46" r="6" fill="var(--foreground)" />
              <circle cx="44" cy="44" r="2" fill="var(--card)" />
            </g>
            <g className="owl-eye">
              <circle cx="78" cy="46" r="6" fill="var(--foreground)" />
              <circle cx="80" cy="44" r="2" fill="var(--card)" />
            </g>
            {/* mouth opens behind the beak */}
            <ellipse className="owl-mouth" cx="60" cy="61" rx="4.4" ry="1" fill="#6b3d05" />
            {/* beak */}
            <g className="owl-beak">
              <path d="M60 54 L54 62 Q60 68 66 62 Z" fill="#f59e0b" />
            </g>
          </svg>
        </div>
      </div>
      <div className="owl-caption">
        <span className="owl-cdot" />
        <span className="owl-dots">
          <span />
          <span />
          <span />
        </span>
        {label}
      </div>
    </div>
  );
}
