'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ChatCircleDotsIcon, ExamIcon, GraduationCapIcon } from '@phosphor-icons/react/dist/ssr';
import { SignInCard } from '@/components/app/account-menu';
import { OwlMascot } from '@/components/app/owl-mascot';
import { SideNav } from '@/components/app/side-nav';
import { Button } from '@/components/ui/button';
import { useUser } from '@/hooks/useUser';
import { DEFAULT_SETUP, type InterviewSetup } from '@/lib/interview-setup';
import { isSupabaseConfigured } from '@/lib/supabase/client';
import { loadDocuments, saveDocuments } from '@/lib/supabase/documents';

const PROFILES: Record<string, string> = {
  pm: 'Product Management',
  consulting: 'Consulting',
  mba_admissions: 'MBA Admissions',
  tech: 'Tech',
  others: 'Others',
};
const SOURCES: Record<string, string> = {
  bank: 'Question bank',
  pack: 'My resume (pack)',
  scripted: 'My own questions',
  intel: 'Pasted intel',
};
const SOURCE_HINTS: Record<string, string> = {
  bank: 'No documents needed. Adding your resume still improves the feedback.',
  pack: 'Requires your resume: the questions are generated from it.',
  scripted: 'Type your questions below. No documents needed.',
  intel: 'Paste the questions you collected below. No documents needed.',
};
const DOC_LIMIT = 12000; // keeps each set_doc RPC under the 15KiB payload cap

interface SetupFormProps {
  onStartCall: (setup: InterviewSetup) => void;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-left">
      <span className="text-foreground text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}

function DocInput({
  label,
  value,
  onChange,
  placeholder,
  allowUpload = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  allowUpload?: boolean;
}) {
  const [status, setStatus] = useState('');
  const [fileName, setFileName] = useState('');
  const [showText, setShowText] = useState(false);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setStatus('Reading file...');
    try {
      const { extractText } = await import('@/lib/extract-text');
      let text = (await extractText(file)).trim();
      if (!text) {
        setStatus('No text found in that file (is it a scanned PDF?). Paste instead.');
        return;
      }
      let note = '';
      if (text.length > DOC_LIMIT) {
        text = text.slice(0, DOC_LIMIT);
        note = ` (trimmed to ${DOC_LIMIT.toLocaleString()} characters)`;
      }
      onChange(text);
      setFileName(file.name);
      setShowText(false);
      setStatus(`${text.length.toLocaleString()} characters${note}`);
    } catch (err) {
      console.error('document extraction failed', err);
      setStatus('Could not read that file. Paste the text instead.');
    }
  };

  const remove = () => {
    onChange('');
    setFileName('');
    setStatus('');
    setShowText(false);
  };

  return (
    <Field label={label}>
      {allowUpload && !fileName && (
        <input
          type="file"
          accept=".pdf,.md,.txt"
          onChange={(e) => onFile(e.target.files?.[0])}
          className="text-muted-foreground file:border-input file:bg-background file:text-foreground text-xs file:mr-2 file:cursor-pointer file:rounded-md file:border file:px-2 file:py-1"
        />
      )}
      {fileName ? (
        <div className="border-input bg-background flex items-center gap-2 rounded-md border p-2 text-sm">
          <span className="text-foreground min-w-0 flex-1 truncate">
            {fileName} <span className="text-muted-foreground text-xs">{status}</span>
          </span>
          <button
            type="button"
            onClick={() => setShowText(!showText)}
            className="text-muted-foreground text-xs underline"
          >
            {showText ? 'Hide text' : 'View text'}
          </button>
          <button
            type="button"
            onClick={remove}
            className="text-muted-foreground text-xs underline"
          >
            Remove
          </button>
        </div>
      ) : (
        <>
          <textarea
            value={value}
            maxLength={DOC_LIMIT}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={4}
            className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
          />
          {status && <span className="text-muted-foreground text-xs">{status}</span>}
        </>
      )}
      {fileName && showText && (
        <textarea
          value={value}
          maxLength={DOC_LIMIT}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
        />
      )}
    </Field>
  );
}

export const SetupForm = ({ onStartCall, ref }: React.ComponentProps<'div'> & SetupFormProps) => {
  const [appMode, setAppMode] = useState<'interview' | 'coach'>('interview');
  const [profile, setProfile] = useState<string>('pm');
  const [sessionType, setSessionType] = useState<'DRILL' | 'SIMULATION'>('DRILL');
  const [durationMin, setDurationMin] = useState(20);
  const [mode, setMode] = useState<'listen' | 'probing'>('listen');
  const [sourceKind, setSourceKind] = useState<string>('bank');
  const [bankCount, setBankCount] = useState(2);
  const [scripted, setScripted] = useState('');
  const [intel, setIntel] = useState('');
  const [resume, setResume] = useState('');
  const [jd, setJd] = useState('');
  const [stories, setStories] = useState('');
  const [bio, setBio] = useState('');
  const [showDocs, setShowDocs] = useState(false);
  const [error, setError] = useState('');
  const { user, loading: userLoading, supabase } = useUser();
  const [docsLoaded, setDocsLoaded] = useState(false);
  const [savingDocs, setSavingDocs] = useState(false);

  // Signed-in users get their saved documents prefilled, without ever
  // overwriting something already typed or uploaded in this visit.
  useEffect(() => {
    if (!user || !supabase || docsLoaded) return;
    setDocsLoaded(true);
    loadDocuments(supabase)
      .then((docs) => {
        if (docs.resume) setResume((prev) => (prev.trim() ? prev : docs.resume!));
        if (docs.jd) setJd((prev) => (prev.trim() ? prev : docs.jd!));
        if (docs.stories) setStories((prev) => (prev.trim() ? prev : docs.stories!));
        if (docs.bio) setBio((prev) => (prev.trim() ? prev : docs.bio!));
        if (Object.keys(docs).length) toast.info('Loaded your saved documents.');
      })
      .catch((err) => console.error('loading saved documents failed', err));
  }, [user, supabase, docsLoaded]);

  const saveDocs = async () => {
    if (!user || !supabase) return;
    setSavingDocs(true);
    try {
      const saved = await saveDocuments(supabase, user.id, { resume, jd, stories, bio });
      toast.success(
        saved
          ? 'Documents saved to your account. They will be prefilled next time.'
          : 'Nothing to save yet: add a document first.'
      );
    } catch (err) {
      console.error('saving documents failed', err);
      toast.warning('Could not save your documents. Try again in a moment.');
    } finally {
      setSavingDocs(false);
    }
  };

  const start = () => {
    if (appMode === 'coach') {
      if (!resume.trim()) {
        setError('The coach works from your resume. Upload or paste it first.');
        return;
      }
      setError('');
      onStartCall({
        ...DEFAULT_SETUP,
        mode: 'coach',
        profile_id: profile,
        materials: Object.fromEntries(
          Object.entries({ resume, jd, stories }).filter(([, v]) => v.trim())
        ),
      });
      return;
    }
    if (sourceKind === 'pack' && !resume.trim()) {
      setError('The pack source builds questions from your resume. Upload or paste it first.');
      return;
    }
    if (sourceKind === 'scripted' && !scripted.trim()) {
      setError('Type at least one question, or pick another source.');
      return;
    }
    if (sourceKind === 'intel' && !intel.trim()) {
      setError('Paste your intel questions, or pick another source.');
      return;
    }
    setError('');
    const setup: InterviewSetup = {
      profile_id: profile,
      mode: 'interview',
      session_type: sessionType,
      duration_min: sessionType === 'SIMULATION' ? durationMin : null,
      followup_mode: mode,
      materials: Object.fromEntries(
        Object.entries({ resume, jd, stories, bio }).filter(([, v]) => v.trim())
      ),
      source: {
        scripted:
          sourceKind === 'scripted'
            ? scripted
                .split('\n')
                .map((q) => q.trim())
                .filter(Boolean)
            : [],
        use_pack: sourceKind === 'pack',
        bank_count: sourceKind === 'bank' ? bankCount : 0,
        intel_text: sourceKind === 'intel' ? intel : '',
      },
    };
    onStartCall({ ...DEFAULT_SETUP, ...setup });
  };

  // Auth still resolving: render nothing rather than flash the wrong view.
  if (isSupabaseConfigured && userLoading) {
    return <div ref={ref} className="max-h-svh w-full overflow-y-auto" />;
  }

  // Signed out: marketing landing with the sign-in gate, no setup form
  // (user decision 2026-07-13).
  if (isSupabaseConfigured && !user) {
    return (
      <div ref={ref} className="max-h-svh w-full overflow-y-auto">
        <div className="mx-auto flex w-full max-w-xl flex-col items-center px-4 pt-14 text-center md:pt-16">
          <OwlMascot size={84} />
          <p className="text-primary pt-3 text-xs font-bold tracking-widest uppercase">
            Voice mock interviews
          </p>
          <h1 className="text-foreground pt-1 text-3xl font-semibold tracking-tight">
            Behavioral Interview Coach
          </h1>
          <p className="text-muted-foreground max-w-md pt-2 text-sm leading-6">
            A voice interviewer that asks real questions, probes your answers, and coaches you out
            loud. Speak your answer; get scored like the real thing.
          </p>
          <div className="flex flex-wrap justify-center gap-2 pt-4">
            {[
              { icon: ChatCircleDotsIcon, text: 'Follow-up probes, like a real interviewer' },
              { icon: ExamIcon, text: 'Scored on a 6-dimension rubric' },
              { icon: GraduationCapIcon, text: 'Coach mode that knows your resume' },
            ].map(({ icon: Icon, text }) => (
              <span
                key={text}
                className="border-border/60 bg-card text-muted-foreground flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs"
              >
                <Icon className="text-primary size-3.5" weight="bold" />
                {text}
              </span>
            ))}
          </div>
        </div>
        <SignInCard />
        <p className="text-muted-foreground pb-10 text-center font-mono text-[10px] tracking-wider uppercase">
          Built with{' '}
          <a
            target="_blank"
            rel="noopener noreferrer"
            href="https://docs.livekit.io/agents"
            className="underline underline-offset-2"
          >
            LiveKit Agents
          </a>
        </p>
      </div>
    );
  }

  // Signed in (or auth not configured): app shell around the setup form.
  return (
    <div ref={ref} className="max-h-svh w-full overflow-y-auto">
      {isSupabaseConfigured && <SideNav />}
      <div className={isSupabaseConfigured ? 'pt-16 md:pt-0 md:pl-60' : ''}>
        <div className="mx-auto w-full max-w-xl px-4 py-8 md:py-12">
          <h1 className="text-foreground text-xl font-semibold tracking-tight">
            {appMode === 'interview' ? 'New practice session' : 'New coach session'}
          </h1>
          <p className="text-muted-foreground pt-1 text-sm">
            {appMode === 'interview'
              ? 'Set up your session, then speak your answers. Say "that’s my answer" when you finish one.'
              : 'A voice coach that knows your materials: likely questions, story gaps, and how to phrase answers.'}
          </p>
          <section className="bg-card border-border/60 mt-4 flex w-full flex-col gap-4 rounded-2xl border px-6 py-8 shadow-sm">
            <div className="grid grid-cols-2 gap-2">
              {(['interview', 'coach'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setAppMode(m)}
                  className={`rounded-xl border p-3 text-sm font-medium transition-colors ${
                    appMode === m
                      ? 'border-primary bg-primary/5 text-foreground'
                      : 'border-input text-muted-foreground hover:border-ring/50 hover:text-foreground'
                  }`}
                >
                  {m === 'interview' ? 'Practice interview' : 'Coach session'}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Round">
                <select
                  value={profile}
                  onChange={(e) => setProfile(e.target.value)}
                  className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                >
                  {Object.entries(PROFILES).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              {appMode === 'interview' && (
                <Field label="Interview mode">
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as 'listen' | 'probing')}
                    className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                  >
                    <option value="listen">Listen: full answer, then feedback</option>
                    <option value="probing">Probing: follow-up questions after your answer</option>
                  </select>
                </Field>
              )}
            </div>

            {appMode === 'interview' && (
              <div className="grid grid-cols-2 gap-4">
                <Field label="Session type">
                  <select
                    value={sessionType}
                    onChange={(e) => setSessionType(e.target.value as 'DRILL' | 'SIMULATION')}
                    className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                  >
                    <option value="DRILL">Drill: feedback after every answer</option>
                    <option value="SIMULATION">Simulation: timed, debrief at the end</option>
                  </select>
                  {sessionType === 'SIMULATION' && (
                    <span className="text-muted-foreground text-xs">
                      The interviewer paces questions to the clock and drops extras if your answers
                      run long.
                    </span>
                  )}
                </Field>
                {sessionType === 'SIMULATION' && (
                  <Field label="Duration (minutes)">
                    <input
                      type="number"
                      min={15}
                      max={60}
                      step={5}
                      value={durationMin}
                      onChange={(e) => setDurationMin(Number(e.target.value))}
                      className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                    />
                  </Field>
                )}
              </div>
            )}

            {appMode === 'interview' && (
              <div className="grid grid-cols-2 gap-4">
                <Field label="Questions from">
                  <select
                    value={sourceKind}
                    onChange={(e) => {
                      setSourceKind(e.target.value);
                      if (e.target.value === 'pack') setShowDocs(true);
                    }}
                    className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                  >
                    {Object.entries(SOURCES).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <span className="text-muted-foreground text-xs">{SOURCE_HINTS[sourceKind]}</span>
                </Field>
                {sourceKind === 'bank' && (
                  <Field label="How many questions">
                    <input
                      type="number"
                      min={1}
                      max={6}
                      value={bankCount}
                      onChange={(e) => setBankCount(Number(e.target.value))}
                      className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                    />
                  </Field>
                )}
              </div>
            )}

            {appMode === 'interview' && sourceKind === 'scripted' && (
              <DocInput
                label="Your questions, one per line (required)"
                value={scripted}
                onChange={setScripted}
                placeholder={'Tell me about a time you...\nDescribe a situation where...'}
              />
            )}
            {appMode === 'interview' && sourceKind === 'intel' && (
              <DocInput
                label="Interview intel: questions this company asks (required)"
                value={intel}
                onChange={setIntel}
                placeholder="Paste questions or notes you have collected"
              />
            )}

            {appMode === 'interview' && (
              <button
                type="button"
                onClick={() => setShowDocs(!showDocs)}
                className="text-muted-foreground self-start text-sm underline"
              >
                {showDocs ? 'Hide documents' : 'Add documents (resume, JD, stories)'}
              </button>
            )}
            {(showDocs || appMode === 'coach') && (
              <div className="flex flex-col gap-3">
                <p className="text-muted-foreground text-xs">
                  {appMode === 'interview'
                    ? 'Documents go only to the grader and coach, never to the live interviewer. The score report uses them to spot facts you could have used.'
                    : 'The coach reads everything you supply here and answers from it: likely questions from your resume and JD, gaps from your stories.'}
                </p>
                <DocInput
                  label={
                    sourceKind === 'pack' || appMode === 'coach'
                      ? 'Resume (required)'
                      : 'Resume (optional)'
                  }
                  value={resume}
                  onChange={setResume}
                  placeholder="Upload a .pdf/.md/.txt or paste your resume text"
                  allowUpload
                />
                <DocInput
                  label={
                    appMode === 'coach'
                      ? 'Job description (recommended)'
                      : 'Job description (optional)'
                  }
                  value={jd}
                  onChange={setJd}
                  placeholder="Upload or paste the JD you are targeting"
                  allowUpload
                />
                <DocInput
                  label="Stories / brag doc (optional)"
                  value={stories}
                  onChange={setStories}
                  placeholder="Upload or paste story notes or a brag doc"
                  allowUpload
                />
                {appMode === 'interview' && (
                  <DocInput
                    label="Interviewer bio (optional): shapes the interviewer's style and voice"
                    value={bio}
                    onChange={setBio}
                    placeholder="Paste the interviewer's LinkedIn About text or a short bio"
                    allowUpload
                  />
                )}
                {user && (
                  <button
                    type="button"
                    onClick={saveDocs}
                    disabled={savingDocs}
                    className="border-input text-foreground hover:border-ring/50 self-start rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {savingDocs ? 'Saving…' : 'Save documents to my account'}
                  </button>
                )}
              </div>
            )}

            {error && <p className="text-destructive text-sm">{error}</p>}

            <Button
              size="lg"
              onClick={start}
              className="mt-2 w-full rounded-full font-mono text-xs font-bold tracking-wider uppercase"
            >
              {appMode === 'interview' ? 'Start interview' : 'Start coaching'}
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
};
