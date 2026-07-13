'use client';

import { useState } from 'react';
import { SaveItemButton } from '@/components/app/save-item-button';
import type { CoachPack, Debrief, RewriteResult, ScoreCard } from '@/hooks/useInterviewState';

const STRENGTH_STYLE: Record<string, string> = {
  STRONG: 'bg-green-500/15 text-green-700 dark:text-green-400',
  PARTIAL: 'bg-yellow-500/15 text-yellow-700 dark:text-yellow-400',
  GAP: 'bg-red-500/15 text-red-700 dark:text-red-400',
};

const LEVEL_STYLE: Record<string, string> = {
  Solid: 'bg-green-500/15 text-green-700 dark:text-green-400',
  NeedsWork: 'bg-yellow-500/15 text-yellow-700 dark:text-yellow-400',
  Gap: 'bg-red-500/15 text-red-700 dark:text-red-400',
};

const DIMENSION_NAMES: Record<string, string> = {
  structure: 'Structure',
  specificity: 'Specificity',
  i_vs_we: 'I vs We',
  quantification: 'Quantification',
  length: 'Length',
  reflection: 'Reflection',
};

export function QuestionBanner({
  question,
  number,
  total,
}: {
  question: string;
  number?: number;
  total?: number;
}) {
  if (!question) return null;
  return (
    <div className="pointer-events-none fixed top-4 right-4 left-4 z-40 flex justify-center">
      <div className="bg-background/95 border-input max-w-2xl rounded-lg border px-4 py-3 shadow-sm backdrop-blur">
        <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          {number && total ? `Question ${number} of ${total}` : 'Question'}
        </p>
        <p className="text-foreground text-sm leading-6">{question}</p>
        <p className="text-muted-foreground pt-1 text-xs">
          Take your time. When you finish, say &ldquo;that&rsquo;s my answer&rdquo;. Say
          &ldquo;repeat the question&rdquo; to hear it again.
        </p>
      </div>
    </div>
  );
}

export function CoachActionsBanner() {
  return (
    <div className="pointer-events-none fixed top-4 right-4 left-4 z-40 flex justify-center">
      <div className="bg-background/95 border-input max-w-2xl rounded-lg border px-4 py-3 shadow-sm backdrop-blur">
        <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          What you can do here
        </p>
        <ul className="text-foreground mt-1 flex list-disc flex-col gap-0.5 pl-4 text-xs leading-5">
          <li>
            Click a question in the panel, then Get game plan: which story to use and how to open.
          </li>
          <li>
            Just talk to the coach: &ldquo;which story fits question two?&rdquo;, &ldquo;where am I
            thin against this JD?&rdquo;
          </li>
          <li>Practice this in Drill: rehearse that one question and get graded.</li>
          <li>Say &ldquo;end session&rdquo; when you are done.</li>
        </ul>
      </div>
    </div>
  );
}

export function CoachPackPanel({
  pack,
  gamePlans,
  onDiscuss,
  onPractice,
}: {
  pack: CoachPack;
  gamePlans: Record<string, string>;
  onDiscuss: (questionText: string) => void;
  onPractice: (questionText: string) => void;
}) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [requested, setRequested] = useState<Record<string, boolean>>({});
  const coverageByQuestion = new Map(pack.coverage.map((c) => [c.question, c]));

  const requestPlan = (text: string) => {
    setRequested((prev) => ({ ...prev, [text]: true }));
    onDiscuss(text);
  };

  return (
    <div className="bg-background/95 border-input fixed top-4 right-4 bottom-4 z-40 w-80 overflow-y-auto rounded-xl border p-4 shadow-sm backdrop-blur">
      <h2 className="text-foreground text-sm font-semibold">Your question pack</h2>
      <p className="text-muted-foreground pt-1 text-xs">Built from your documents.</p>
      {pack.coverage.length === 0 && (
        <p className="text-muted-foreground pt-1 text-[11px] leading-4">
          Upload a stories doc to see coverage badges: which of these questions you already have a
          prepared answer for.
        </p>
      )}
      {pack.coverage.length > 0 && (
        <div className="border-input mt-2 flex flex-col gap-1 rounded-lg border p-2">
          <p className="text-muted-foreground text-[11px] leading-4">
            Each badge checks your stories doc: do you have an answer prepared?
          </p>
          <p className="text-muted-foreground text-[11px] leading-4">
            <span className={`rounded-full px-1.5 py-0.5 font-medium ${STRENGTH_STYLE.STRONG}`}>
              STRONG
            </span>{' '}
            a prepared story answers it directly
          </p>
          <p className="text-muted-foreground text-[11px] leading-4">
            <span className={`rounded-full px-1.5 py-0.5 font-medium ${STRENGTH_STYLE.PARTIAL}`}>
              PARTIAL
            </span>{' '}
            a story could stretch to it with reframing
          </p>
          <p className="text-muted-foreground text-[11px] leading-4">
            <span className={`rounded-full px-1.5 py-0.5 font-medium ${STRENGTH_STYLE.GAP}`}>
              GAP
            </span>{' '}
            nothing in your stories doc covers it yet
          </p>
        </div>
      )}
      <div className="mt-3 flex flex-col gap-2">
        {pack.questions.map((q, i) => {
          const cov = coverageByQuestion.get(q.text);
          const plan = gamePlans[q.text];
          const isOpen = expanded === i;
          return (
            <div key={i} className="border-input rounded-lg border p-3">
              <button
                type="button"
                onClick={() => setExpanded(isOpen ? null : i)}
                className="flex w-full items-start justify-between gap-2 text-left"
              >
                <p className="text-foreground text-xs leading-5">{q.text}</p>
                {cov && (
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STRENGTH_STYLE[cov.strength] ?? 'bg-muted text-muted-foreground'}`}
                  >
                    {cov.strength}
                  </span>
                )}
              </button>
              <p className="text-muted-foreground pt-1 text-[11px] leading-4">
                {q.bucket && <span className="uppercase">{q.bucket} · </span>}
                {q.why_likely || `From: "${q.resume_line}"`}
              </p>
              {isOpen && (
                <div className="border-input mt-2 flex flex-col gap-2 border-t pt-2">
                  {q.resume_line && (
                    <p className="text-muted-foreground text-[11px] leading-4">
                      Resume line: &ldquo;{q.resume_line}&rdquo;
                    </p>
                  )}
                  {cov?.covered_by ? (
                    <p className="text-muted-foreground text-[11px] leading-4">
                      Covered by your story: &ldquo;{cov.covered_by}&rdquo;
                      {cov.note && ` (${cov.note})`}
                    </p>
                  ) : (
                    cov?.strength === 'GAP' && (
                      <p className="text-muted-foreground text-[11px] leading-4">
                        No prepared story covers this yet
                        {cov.note ? `: ${cov.note}` : '.'} Get the game plan to build one.
                      </p>
                    )
                  )}
                  {plan ? (
                    <p className="text-foreground text-[11px] leading-4">{plan}</p>
                  ) : (
                    <button
                      type="button"
                      onClick={() => requestPlan(q.text)}
                      disabled={requested[q.text]}
                      className="border-input text-foreground self-start rounded-md border px-2 py-1 text-[11px] disabled:opacity-50"
                    >
                      {requested[q.text] ? 'Coach is thinking...' : 'Get game plan'}
                    </button>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => onPractice(q.text)}
                      className="border-input text-foreground rounded-md border px-2 py-1 text-[11px]"
                    >
                      Practice this in Drill
                    </button>
                    {cov?.strength === 'GAP' && (
                      <SaveItemButton
                        kind="gap"
                        title={q.text}
                        content={[
                          `Question: ${q.text}`,
                          cov.note ? `Gap: ${cov.note}` : 'No prepared story covers this yet.',
                          plan ? `Game plan: ${plan}` : '',
                        ]
                          .filter(Boolean)
                          .join('\n')}
                        label="Save this gap"
                      />
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s.toString().padStart(2, '0')}s` : `${s}s`;
}

export function DebriefPanel({ debrief }: { debrief: Debrief }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border-input max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border p-5 shadow-lg">
        <h2 className="text-foreground text-lg font-semibold">Session debrief</h2>
        <p className="text-muted-foreground pt-1 text-xs">
          {debrief.reps.length} answer{debrief.reps.length === 1 ? '' : 's'}
          {debrief.dropped > 0 &&
            ` · ${debrief.dropped} planned question${debrief.dropped === 1 ? '' : 's'} dropped for time`}
        </p>

        {debrief.patterns.length > 0 && (
          <div className="border-input mt-4 rounded-lg border p-3">
            <h3 className="text-foreground text-sm font-semibold">Patterns across answers</h3>
            <p className="text-muted-foreground pt-0.5 text-[11px]">
              Fix these first: they repeated across your set.
            </p>
            <ul className="text-foreground mt-1 flex list-disc flex-col gap-0.5 pl-4 text-xs leading-5">
              {debrief.patterns.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4 flex flex-col gap-2">
          {debrief.reps.map((rep, i) => {
            const weak = Object.entries(rep.dimensions).filter(([, d]) => d.level !== 'Solid');
            return (
              <div key={i} className="border-input rounded-lg border p-3">
                <p className="text-foreground text-xs leading-5">
                  <span className="text-muted-foreground font-medium">Q{i + 1}.</span>{' '}
                  {rep.question}
                </p>
                <p className="text-muted-foreground pt-0.5 text-[11px]">
                  Answered in {formatDuration(rep.duration_s)}
                </p>
                {rep.graded ? (
                  <>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {Object.entries(rep.dimensions).map(([key, dim]) => (
                        <span
                          key={key}
                          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${LEVEL_STYLE[dim.level] ?? 'bg-muted text-muted-foreground'}`}
                        >
                          {DIMENSION_NAMES[key] ?? key}
                          {dim.level !== 'Solid' &&
                            ` · ${dim.level === 'NeedsWork' ? 'Needs work' : 'Gap'}`}
                        </span>
                      ))}
                    </div>
                    {weak.length > 0 ? (
                      <div className="border-input mt-2 flex flex-col gap-2 border-t pt-2">
                        {weak.map(([key, dim]) => (
                          <div key={key}>
                            <span className="text-foreground text-xs font-medium">
                              {DIMENSION_NAMES[key] ?? key}
                            </span>
                            {dim.note && (
                              <p className="text-muted-foreground pt-0.5 text-[11px] leading-4">
                                {dim.note}
                              </p>
                            )}
                            {dim.evidence.length > 0 && (
                              <p className="text-foreground/80 pt-0.5 text-[11px] italic">
                                &ldquo;{dim.evidence[0]}&rdquo;
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted-foreground pt-2 text-[11px]">
                        All six dimensions solid on this one.
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-muted-foreground pt-2 text-[11px]">
                    Not scored: the grader was unavailable for this answer.
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {(debrief.dropped_questions?.length ?? 0) > 0 && (
          <div className="border-input mt-4 rounded-lg border p-3">
            <h3 className="text-foreground text-sm font-semibold">Dropped for time</h3>
            <p className="text-muted-foreground pt-0.5 text-[11px]">
              These were planned but your earlier answers ran long. Tighter answers buy you more
              questions.
            </p>
            <ul className="text-foreground mt-1 flex list-disc flex-col gap-0.5 pl-4 text-xs leading-5">
              {debrief.dropped_questions!.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}

        {debrief.ammo.length > 0 && (
          <div className="mt-5">
            <h3 className="text-foreground text-sm font-semibold">
              Missed ammo across the set: facts from your documents you never used
            </h3>
            <div className="mt-2 flex flex-col gap-2">
              {debrief.ammo.map((item, i) => (
                <div key={i} className="border-input rounded-lg border p-3">
                  <p className="text-foreground text-xs leading-5">&ldquo;{item.fact}&rdquo;</p>
                  <p className="text-muted-foreground pt-1 text-xs leading-5">
                    {item.relevance} <span className="uppercase">({item.doc_source})</span>
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-muted-foreground pt-4 text-center text-xs">Say end when you are done.</p>
      </div>
    </div>
  );
}

export function ScoreCardPanel({
  card,
  rewrite,
  onRewrite,
  onDismiss,
}: {
  card: ScoreCard;
  rewrite: RewriteResult | null;
  onRewrite: () => void;
  onDismiss: () => void;
}) {
  const [rewriteRequested, setRewriteRequested] = useState(false);
  const [rewriteTab, setRewriteTab] = useState<'notes' | 'answer'>('notes');
  const [copied, setCopied] = useState(false);

  const copyRewrite = () => {
    if (!rewrite?.rewritten_answer) return;
    navigator.clipboard.writeText(rewrite.rewritten_answer).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border-input max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border p-5 shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-foreground text-lg font-semibold">Score card</h2>
            <p className="text-muted-foreground pt-1 text-xs">{card.question}</p>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            className="text-muted-foreground text-sm underline"
          >
            Close
          </button>
        </div>

        <div className="mt-4 flex flex-col gap-3">
          {Object.entries(card.dimensions).map(([key, dim]) => (
            <div key={key} className="border-input rounded-lg border p-3">
              <div className="flex items-center justify-between">
                <span className="text-foreground text-sm font-medium">
                  {DIMENSION_NAMES[key] ?? key}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${LEVEL_STYLE[dim.level] ?? 'bg-muted text-muted-foreground'}`}
                >
                  {dim.level === 'NeedsWork' ? 'Needs work' : dim.level}
                </span>
              </div>
              <p className="text-muted-foreground pt-1 text-xs leading-5">{dim.note}</p>
              {dim.evidence.length > 0 && (
                <p className="text-foreground/80 pt-1 text-xs italic">
                  &ldquo;{dim.evidence[0]}&rdquo;
                </p>
              )}
            </div>
          ))}
        </div>

        {card.ammo.length > 0 && (
          <div className="mt-5">
            <h3 className="text-foreground text-sm font-semibold">
              Missed ammo: facts from your documents you never used
            </h3>
            <div className="mt-2 flex flex-col gap-2">
              {card.ammo.map((item, i) => (
                <div key={i} className="border-input rounded-lg border p-3">
                  <p className="text-foreground text-xs leading-5">&ldquo;{item.fact}&rdquo;</p>
                  <p className="text-muted-foreground pt-1 text-xs leading-5">
                    {item.relevance} <span className="uppercase">({item.doc_source})</span>
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-5">
          {!rewrite ? (
            <button
              type="button"
              onClick={() => {
                setRewriteRequested(true);
                onRewrite();
              }}
              disabled={rewriteRequested}
              className="border-input text-foreground w-full rounded-md border px-3 py-2 text-sm disabled:opacity-50"
            >
              {rewriteRequested ? 'Coach is writing...' : 'Show me the rewrite'}
            </button>
          ) : (
            <div className="flex flex-col gap-3">
              {rewrite.message && (
                <p className="text-muted-foreground border-input rounded-lg border p-3 text-xs leading-5">
                  {rewrite.message}
                </p>
              )}
              {rewrite.notes.length > 0 && rewrite.rewritten_answer && (
                <div className="border-input flex gap-1 rounded-lg border p-1">
                  <button
                    type="button"
                    onClick={() => setRewriteTab('notes')}
                    className={`flex-1 rounded-md px-2 py-1.5 text-xs ${
                      rewriteTab === 'notes'
                        ? 'bg-muted text-foreground font-medium'
                        : 'text-muted-foreground'
                    }`}
                  >
                    Improvement notes
                  </button>
                  <button
                    type="button"
                    onClick={() => setRewriteTab('answer')}
                    className={`flex-1 rounded-md px-2 py-1.5 text-xs ${
                      rewriteTab === 'answer'
                        ? 'bg-muted text-foreground font-medium'
                        : 'text-muted-foreground'
                    }`}
                  >
                    Full answer
                  </button>
                </div>
              )}
              {rewrite.notes.length > 0 &&
                (rewriteTab === 'notes' || !rewrite.rewritten_answer) && (
                  <div className="flex flex-col gap-2">
                    {rewrite.notes.map((n, i) => (
                      <div key={i} className="border-input rounded-lg border p-3">
                        <span className="text-muted-foreground text-[10px] font-medium uppercase">
                          {DIMENSION_NAMES[n.dimension] ?? n.dimension}
                        </span>
                        <p className="text-muted-foreground pt-1 text-xs leading-5">{n.problem}</p>
                        <p className="text-foreground pt-1 text-xs leading-5">{n.fix}</p>
                      </div>
                    ))}
                  </div>
                )}
              {rewrite.rewritten_answer &&
                (rewriteTab === 'answer' || rewrite.notes.length === 0) && (
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-foreground text-sm font-semibold">
                        The answer you could have given
                      </h3>
                      <div className="flex shrink-0 gap-1.5">
                        <SaveItemButton
                          kind="rewrite"
                          title={card.question}
                          content={rewrite.rewritten_answer}
                          label="Save rewrite"
                        />
                        <button
                          type="button"
                          onClick={copyRewrite}
                          className="border-input text-foreground shrink-0 rounded-md border px-2 py-1 text-[11px]"
                        >
                          {copied ? 'Copied!' : 'Copy answer'}
                        </button>
                      </div>
                    </div>
                    <p className="text-foreground/90 border-input mt-2 rounded-lg border p-3 text-xs leading-5 whitespace-pre-wrap">
                      {rewrite.rewritten_answer}
                    </p>
                  </div>
                )}
            </div>
          )}
        </div>

        <p className="text-muted-foreground pt-4 text-center text-xs">
          Say retry, next, or end to continue.
        </p>
      </div>
    </div>
  );
}
