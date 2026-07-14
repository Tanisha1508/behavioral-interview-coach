'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { TrashIcon } from '@phosphor-icons/react/dist/ssr';
import { OwlMascot } from '@/components/app/owl-mascot';
import { SideNav } from '@/components/app/side-nav';
import { useUser } from '@/hooks/useUser';
import { cn } from '@/lib/shadcn/utils';
import { isSupabaseConfigured } from '@/lib/supabase/client';

type DimScore = { level: string; note?: string };
type AnswerRow = {
  id: string;
  question: string;
  transcript: string | null;
  duration_s: number | null;
  scores: { dimensions?: Record<string, DimScore>; spoken_summary?: string[] } | null;
  rewrite: string | null;
  created_at: string;
};
type SessionRow = {
  id: string;
  type: string;
  round: string | null;
  started_at: string;
  duration_s: number | null;
  dropped: number;
  patterns: string[] | null;
  answers: AnswerRow[];
};
type SavedItem = {
  id: string;
  kind: string;
  title: string | null;
  content: string;
  created_at: string;
};

const DIMENSION_ORDER = [
  'structure',
  'specificity',
  'i_vs_we',
  'quantification',
  'length',
  'reflection',
];
const DIMENSION_NAMES: Record<string, string> = {
  structure: 'Structure',
  specificity: 'Specificity',
  i_vs_we: 'I vs We',
  quantification: 'Quantification',
  length: 'Length',
  reflection: 'Reflection',
};
const LEVEL_STYLE: Record<string, string> = {
  Solid: 'bg-green-500/15 text-green-700 dark:text-green-400',
  NeedsWork: 'bg-yellow-500/15 text-yellow-700 dark:text-yellow-400',
  Gap: 'bg-red-500/15 text-red-700 dark:text-red-400',
};
const KIND_LABEL: Record<string, string> = {
  rewrite: 'Rewrite',
  answer: 'Answer',
  gap: 'Coach gap',
};
const ROUND_NAMES: Record<string, string> = {
  pm: 'Product Management',
  consulting: 'Consulting',
  mba_admissions: 'MBA Admissions',
  tech: 'Tech',
  others: 'Others',
};

type TabKey = 'sessions' | 'saved' | 'performance';

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function fmtDuration(s: number | null) {
  if (!s && s !== 0) return null;
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${(s % 60).toString().padStart(2, '0')}s` : `${s}s`;
}

function solidSummary(answers: AnswerRow[]) {
  let solid = 0;
  let total = 0;
  for (const a of answers) {
    for (const dim of Object.values(a.scores?.dimensions ?? {})) {
      total += 1;
      if (dim.level === 'Solid') solid += 1;
    }
  }
  return total ? `${solid}/${total} dimensions solid` : 'not scored';
}

// A small two-step confirm so a stray click never deletes anything.
function DeleteButton({
  label,
  confirmLabel,
  onConfirm,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        if (armed) onConfirm();
        else setArmed(true);
      }}
      className={cn(
        'flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
        armed
          ? 'bg-destructive/15 text-destructive'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
      aria-label={label}
    >
      <TrashIcon className="size-3.5" weight={armed ? 'fill' : 'regular'} />
      {armed ? confirmLabel : label}
    </button>
  );
}

function AnswerCard({ answer }: { answer: AnswerRow }) {
  const [showTranscript, setShowTranscript] = useState(false);
  const dims = Object.entries(answer.scores?.dimensions ?? {});
  return (
    <div className="border-border/60 rounded-lg border p-3">
      <p className="text-foreground text-sm leading-6">{answer.question}</p>
      <p className="text-muted-foreground pt-0.5 text-xs">
        {fmtDuration(answer.duration_s) ?? 'duration unknown'}
      </p>
      {dims.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {dims.map(([key, dim]) => (
            <span
              key={key}
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${LEVEL_STYLE[dim.level] ?? 'bg-muted text-muted-foreground'}`}
            >
              {DIMENSION_NAMES[key] ?? key}
              {dim.level !== 'Solid' && ` · ${dim.level === 'NeedsWork' ? 'Needs work' : 'Gap'}`}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground pt-2 text-xs">Not scored.</p>
      )}
      {answer.transcript && (
        <button
          type="button"
          onClick={() => setShowTranscript(!showTranscript)}
          className="text-muted-foreground hover:text-foreground mt-2 text-xs underline underline-offset-2"
        >
          {showTranscript ? 'Hide transcript' : 'Show transcript'}
        </button>
      )}
      {showTranscript && answer.transcript && (
        <p className="text-muted-foreground border-border/60 mt-2 rounded-md border p-2 text-xs leading-5 whitespace-pre-wrap">
          {answer.transcript}
        </p>
      )}
      {answer.rewrite && (
        <div className="border-border/60 mt-2 rounded-md border p-2">
          <p className="text-primary text-[10px] font-bold tracking-widest uppercase">
            Coach rewrite
          </p>
          <p className="text-foreground/90 pt-1 text-xs leading-5 whitespace-pre-wrap">
            {answer.rewrite}
          </p>
        </div>
      )}
    </div>
  );
}

function SessionCard({
  session,
  onDelete,
}: {
  session: SessionRow;
  onDelete: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const answers = [...session.answers].sort((a, b) => a.created_at.localeCompare(b.created_at));
  return (
    <div className="border-border/60 bg-card rounded-xl border p-4">
      <div className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex flex-1 items-start justify-between gap-3 text-left"
        >
          <div>
            <p className="text-foreground text-sm font-medium">
              <span className="capitalize">{session.type}</span>
              {session.round && (
                <span className="text-muted-foreground font-normal">
                  {' '}
                  · {ROUND_NAMES[session.round] ?? session.round}
                </span>
              )}
            </p>
            <p className="text-muted-foreground pt-0.5 text-xs">
              {fmtDate(session.started_at)}
              {fmtDuration(session.duration_s) && ` · ${fmtDuration(session.duration_s)}`}
              {` · ${answers.length} answer${answers.length === 1 ? '' : 's'}`}
              {session.dropped > 0 && ` · ${session.dropped} dropped for time`}
            </p>
          </div>
          <span className="text-primary shrink-0 pt-1 text-xs font-medium">
            {solidSummary(answers)}
          </span>
        </button>
        <DeleteButton
          label="Remove"
          confirmLabel="Confirm"
          onConfirm={() => onDelete(session.id)}
        />
      </div>
      {open && (
        <div className="mt-3 flex flex-col gap-2">
          {(session.patterns?.length ?? 0) > 0 && (
            <div className="border-border/60 rounded-lg border p-3">
              <p className="text-primary text-[10px] font-bold tracking-widest uppercase">
                Patterns across answers
              </p>
              <ul className="text-foreground mt-1 flex list-disc flex-col gap-0.5 pl-4 text-xs leading-5">
                {session.patterns!.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {answers.map((a) => (
            <AnswerCard key={a.id} answer={a} />
          ))}
        </div>
      )}
    </div>
  );
}

// Aggregate the 6-dimension rubric and answer timing across every session.
function PerformancePanel({ sessions }: { sessions: SessionRow[] }) {
  const stats = useMemo(() => {
    const dims: Record<string, { Solid: number; NeedsWork: number; Gap: number; total: number }> =
      {};
    for (const key of DIMENSION_ORDER) dims[key] = { Solid: 0, NeedsWork: 0, Gap: 0, total: 0 };

    let answeredWithScore = 0;
    let durationSum = 0;
    let durationCount = 0;

    for (const s of sessions) {
      for (const a of s.answers) {
        const scored = a.scores?.dimensions ?? {};
        if (Object.keys(scored).length > 0) answeredWithScore += 1;
        for (const [key, dim] of Object.entries(scored)) {
          if (!dims[key]) dims[key] = { Solid: 0, NeedsWork: 0, Gap: 0, total: 0 };
          if (dim.level === 'Solid' || dim.level === 'NeedsWork' || dim.level === 'Gap') {
            dims[key][dim.level] += 1;
            dims[key].total += 1;
          }
        }
        if (a.duration_s != null) {
          durationSum += a.duration_s;
          durationCount += 1;
        }
      }
    }

    const avgPerQuestion = durationCount ? Math.round(durationSum / durationCount) : null;
    return { dims, answeredWithScore, avgPerQuestion, durationCount };
  }, [sessions]);

  const scoredDims = DIMENSION_ORDER.filter((k) => stats.dims[k]?.total > 0);

  if (scoredDims.length === 0) {
    return (
      <div className="border-border/60 bg-card flex items-center gap-4 rounded-xl border p-5">
        <OwlMascot size={56} className="shrink-0" />
        <p className="text-muted-foreground text-sm">
          No graded answers yet. Finish a drill or simulation while signed in and your dimension
          breakdown and timing will show up here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Summary tiles */}
      <div className="grid grid-cols-2 gap-2">
        <div className="border-border/60 bg-card rounded-xl border p-4">
          <p className="text-muted-foreground text-xs">Avg time per question</p>
          <p className="text-foreground pt-1 text-2xl font-semibold tracking-tight">
            {stats.avgPerQuestion != null ? fmtDuration(stats.avgPerQuestion) : '—'}
          </p>
          <p className="text-muted-foreground pt-0.5 text-[11px]">
            across {stats.durationCount} answer{stats.durationCount === 1 ? '' : 's'}
          </p>
        </div>
        <div className="border-border/60 bg-card rounded-xl border p-4">
          <p className="text-muted-foreground text-xs">Answers graded</p>
          <p className="text-foreground pt-1 text-2xl font-semibold tracking-tight">
            {stats.answeredWithScore}
          </p>
          <p className="text-muted-foreground pt-0.5 text-[11px]">
            over {sessions.length} session{sessions.length === 1 ? '' : 's'}
          </p>
        </div>
      </div>

      {/* Per-dimension breakdown */}
      <div className="border-border/60 bg-card rounded-xl border p-4">
        <p className="text-primary text-[10px] font-bold tracking-widest uppercase">
          Across 6 dimensions
        </p>
        <div className="mt-3 flex flex-col gap-3">
          {scoredDims.map((key) => {
            const d = stats.dims[key];
            const pct = (n: number) => (d.total ? (n / d.total) * 100 : 0);
            return (
              <div key={key}>
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-foreground text-xs font-medium">{DIMENSION_NAMES[key]}</p>
                  <p className="text-muted-foreground text-[11px]">
                    {d.Solid}/{d.total} solid
                  </p>
                </div>
                <div className="bg-muted mt-1 flex h-2 overflow-hidden rounded-full">
                  <div className="bg-green-500" style={{ width: `${pct(d.Solid)}%` }} />
                  <div className="bg-yellow-500" style={{ width: `${pct(d.NeedsWork)}%` }} />
                  <div className="bg-red-500" style={{ width: `${pct(d.Gap)}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="text-muted-foreground mt-4 flex flex-wrap gap-3 text-[11px]">
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-green-500" /> Solid
          </span>
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-yellow-500" /> Needs work
          </span>
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-red-500" /> Gap
          </span>
        </div>
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const { user, loading, supabase } = useUser();
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);
  const [saved, setSaved] = useState<SavedItem[] | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<TabKey>('sessions');

  useEffect(() => {
    if (!user || !supabase) return;
    Promise.all([
      supabase
        .from('sessions')
        .select('id, type, round, started_at, duration_s, dropped, patterns, answers(*)')
        .order('started_at', { ascending: false }),
      supabase
        .from('saved_items')
        .select('id, kind, title, content, created_at')
        .order('created_at', { ascending: false }),
    ]).then(([s, i]) => {
      if (s.error || i.error) {
        console.error('history load failed', s.error ?? i.error);
        setError('Could not load your history. Refresh to try again.');
        return;
      }
      setSessions((s.data as SessionRow[]) ?? []);
      setSaved((i.data as SavedItem[]) ?? []);
    });
  }, [user, supabase]);

  const deleteSession = async (id: string) => {
    if (!supabase) return;
    const prev = sessions;
    setSessions((cur) => cur?.filter((s) => s.id !== id) ?? cur);
    const { error: delErr } = await supabase.from('sessions').delete().eq('id', id);
    if (delErr) {
      console.error('session delete failed', delErr);
      setSessions(prev ?? null);
      toast.error('Could not remove that session.');
    } else {
      toast.success('Session removed.');
    }
  };

  const deleteSaved = async (id: string) => {
    if (!supabase) return;
    const prev = saved;
    setSaved((cur) => cur?.filter((it) => it.id !== id) ?? cur);
    const { error: delErr } = await supabase.from('saved_items').delete().eq('id', id);
    if (delErr) {
      console.error('saved item delete failed', delErr);
      setSaved(prev ?? null);
      toast.error('Could not unsave that item.');
    } else {
      toast.success('Removed from saved.');
    }
  };

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'sessions', label: 'Sessions' },
    { key: 'saved', label: 'Saved items' },
    { key: 'performance', label: 'Performance' },
  ];

  return (
    <>
      {user && <SideNav />}
      <main className={user ? 'min-h-svh pt-16 md:pt-0 md:pl-60' : 'min-h-svh'}>
        <div className="mx-auto w-full max-w-2xl px-4 py-8 md:py-12">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-primary text-xs font-bold tracking-widest uppercase">
                Your account
              </p>
              <h1 className="text-foreground pt-1 text-2xl font-semibold tracking-tight">
                Practice history
              </h1>
            </div>
            {!user && (
              <Link
                href="/"
                className="text-muted-foreground hover:text-foreground pb-1 text-sm underline underline-offset-4"
              >
                Back to practice
              </Link>
            )}
          </div>

          {!isSupabaseConfigured || (!loading && !user) ? (
            <div className="border-border/60 bg-card mt-6 flex items-center gap-4 rounded-xl border p-5">
              <OwlMascot size={56} className="shrink-0" />
              <p className="text-muted-foreground text-sm">
                History needs an account. Go back and sign in with Google, then finish a session:
                every graded answer lands here.
              </p>
            </div>
          ) : loading || sessions === null ? (
            <p className="text-muted-foreground mt-6 text-sm">Loading your history…</p>
          ) : (
            <>
              {error && <p className="text-destructive mt-6 text-sm">{error}</p>}

              {/* Tabs */}
              <div className="border-border/60 mt-6 flex gap-1 border-b">
                {tabs.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setTab(t.key)}
                    className={cn(
                      '-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                      tab === t.key
                        ? 'border-primary text-foreground'
                        : 'text-muted-foreground hover:text-foreground border-transparent'
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {tab === 'sessions' && (
                <section className="mt-4">
                  {sessions.length === 0 ? (
                    <div className="border-border/60 bg-card flex items-center gap-4 rounded-xl border p-5">
                      <OwlMascot size={56} className="shrink-0" />
                      <p className="text-muted-foreground text-sm">
                        No sessions yet. Run a drill or simulation while signed in and it will
                        appear here with its scores.
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {sessions.map((s) => (
                        <SessionCard key={s.id} session={s} onDelete={deleteSession} />
                      ))}
                    </div>
                  )}
                </section>
              )}

              {tab === 'saved' && (
                <section className="mt-4">
                  {(saved?.length ?? 0) === 0 ? (
                    <p className="text-muted-foreground border-border/60 bg-card rounded-xl border p-5 text-sm">
                      Nothing saved yet. On a score card, save a rewrite you like; in a coach
                      session, save the gaps it flags.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {saved!.map((item) => (
                        <div
                          key={item.id}
                          className="border-border/60 bg-card rounded-xl border p-4"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <p className="text-primary text-[10px] font-bold tracking-widest uppercase">
                              {KIND_LABEL[item.kind] ?? item.kind} · {fmtDate(item.created_at)}
                            </p>
                            <DeleteButton
                              label="Unsave"
                              confirmLabel="Confirm"
                              onConfirm={() => deleteSaved(item.id)}
                            />
                          </div>
                          {item.title && (
                            <p className="text-foreground pt-1 text-sm font-medium">{item.title}</p>
                          )}
                          <p className="text-foreground/90 pt-1 text-xs leading-5 whitespace-pre-wrap">
                            {item.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {tab === 'performance' && (
                <section className="mt-4">
                  <PerformancePanel sessions={sessions} />
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
