'use client';

import { useEffect, useState } from 'react';
import { type Room, RoomEvent } from 'livekit-client';

export interface ScoreDimension {
  level: string;
  evidence: string[];
  note: string;
}

export interface AmmoItem {
  fact: string;
  doc_source: string;
  relevance: string;
}

export interface ScoreCard {
  question: string;
  dimensions: Record<string, ScoreDimension>;
  spoken_summary: string[];
  ammo: AmmoItem[];
}

export interface RewriteResult {
  question: string;
  notes: { dimension: string; problem: string; fix: string }[];
  rewritten_answer: string;
  message?: string; // set instead of notes/answer when there was nothing to rewrite
}

export interface DebriefRep {
  question: string;
  duration_s: number;
  graded: boolean;
  dimensions: Record<string, ScoreDimension>;
}

export interface Debrief {
  reps: DebriefRep[];
  patterns: string[];
  ammo: AmmoItem[];
  dropped: number;
  dropped_questions?: string[];
}

export interface CoachPack {
  questions: { text: string; bucket: string; resume_line: string; why_likely: string }[];
  coverage: { question: string; covered_by: string; strength: string; note: string }[];
}

/** Interview UI state fed by the agent's data messages: the current
 * question ("question" topic) and the score card ("scorecard" topic). */
export function useInterviewState(room: Room | undefined) {
  const [question, setQuestion] = useState('');
  const [questionNumber, setQuestionNumber] = useState(0);
  const [questionTotal, setQuestionTotal] = useState(0);
  const [card, setCard] = useState<ScoreCard | null>(null);
  const [coachPack, setCoachPack] = useState<CoachPack | null>(null);
  const [gamePlans, setGamePlans] = useState<Record<string, string>>({});
  const [rewrite, setRewrite] = useState<RewriteResult | null>(null);
  const [debrief, setDebrief] = useState<Debrief | null>(null);
  const [ended, setEnded] = useState(false);

  useEffect(() => {
    if (!room) return;
    const decoder = new TextDecoder();
    const topics = [
      'question',
      'scorecard',
      'coachpack',
      'gameplan',
      'rewrite',
      'debrief',
      'session_ended',
    ];
    const onData = (
      payload: Uint8Array,
      _participant?: unknown,
      _kind?: unknown,
      topic?: string
    ) => {
      if (!topic || !topics.includes(topic)) return;
      try {
        const data = JSON.parse(decoder.decode(payload));
        if (topic === 'question') {
          setQuestion(data.text ?? '');
          setQuestionNumber(data.number ?? 0);
          setQuestionTotal(data.total ?? 0);
          setCard(null); // a new question clears the previous card
          setRewrite(null);
        } else if (topic === 'scorecard') {
          setCard(data as ScoreCard);
        } else if (topic === 'coachpack') {
          setCoachPack(data as CoachPack);
        } else if (topic === 'gameplan') {
          setGamePlans((prev) => ({ ...prev, [data.question]: data.plan }));
        } else if (topic === 'rewrite') {
          setRewrite(data as RewriteResult);
        } else if (topic === 'debrief') {
          setDebrief(data as Debrief);
          setQuestion(''); // the debrief replaces the last question banner
        } else {
          setEnded(true);
        }
      } catch (err) {
        console.error('bad interview data message', err);
      }
    };
    // A disconnect ends one session; the next one must start clean, or a
    // stale ended flag would instantly end it and a stale coach panel
    // would overlay the drill.
    const onDisconnect = () => {
      setQuestion('');
      setQuestionNumber(0);
      setQuestionTotal(0);
      setCard(null);
      setCoachPack(null);
      setGamePlans({});
      setRewrite(null);
      setDebrief(null);
      setEnded(false);
    };
    room.on(RoomEvent.DataReceived, onData);
    room.on(RoomEvent.Disconnected, onDisconnect);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
      room.off(RoomEvent.Disconnected, onDisconnect);
    };
  }, [room]);

  return {
    question,
    questionNumber,
    questionTotal,
    card,
    coachPack,
    gamePlans,
    rewrite,
    debrief,
    ended,
    dismissCard: () => setCard(null),
  };
}
