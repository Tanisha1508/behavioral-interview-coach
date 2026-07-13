'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { DocInput, Field } from '@/components/app/doc-input';
import { OwlMascot } from '@/components/app/owl-mascot';
import { SideNav } from '@/components/app/side-nav';
import { Button } from '@/components/ui/button';
import { useUser } from '@/hooks/useUser';
import { isSupabaseConfigured } from '@/lib/supabase/client';
import { loadDocuments, saveDocuments } from '@/lib/supabase/documents';
import {
  ROUNDS,
  ROUND_NAMES,
  type TargetRound,
  loadProfile,
  markOnboarded,
  saveProfile,
} from '@/lib/supabase/profiles';

// First-run onboarding: capture background, target round, and documents once,
// so every future session reuses them. Skippable at every step; skipping still
// stamps onboarded_at so it never shows again (the Profile page edits later).
const STEPS = ['About you', 'Your round', 'Your documents'] as const;

export function SetupWizard() {
  const router = useRouter();
  const { user, loading, supabase } = useUser();

  // step 0 is the welcome screen; 1..3 are the content steps.
  const [step, setStep] = useState(0);
  const [background, setBackground] = useState('');
  const [goal, setGoal] = useState('');
  const [round, setRound] = useState<TargetRound | null>(null);
  const [resume, setResume] = useState('');
  const [jd, setJd] = useState('');
  const [stories, setStories] = useState('');
  const [prefilled, setPrefilled] = useState(false);
  const [saving, setSaving] = useState(false);

  // Onboarding needs an account. Guests and guest-only deployments go home.
  useEffect(() => {
    if (!isSupabaseConfigured) router.replace('/');
    else if (!loading && !user) router.replace('/');
  }, [loading, user, router]);

  // Prefill anything already saved so re-running the wizard is not a reset.
  useEffect(() => {
    if (!user || !supabase || prefilled) return;
    setPrefilled(true);
    loadProfile(supabase)
      .then((p) => {
        if (p?.background) setBackground((v) => v || p.background!);
        if (p?.goal) setGoal((v) => v || p.goal!);
        if (p?.target_round) setRound((v) => v ?? p.target_round);
      })
      .catch((err) => console.error('prefill profile failed', err));
    loadDocuments(supabase)
      .then((d) => {
        if (d.resume) setResume((v) => v || d.resume!);
        if (d.jd) setJd((v) => v || d.jd!);
        if (d.stories) setStories((v) => v || d.stories!);
      })
      .catch((err) => console.error('prefill documents failed', err));
  }, [user, supabase, prefilled]);

  const finishAndLeave = async (save: () => Promise<void>) => {
    if (!user || !supabase) return;
    setSaving(true);
    try {
      await save();
      await markOnboarded(supabase, user.id);
      router.push('/');
    } catch (err) {
      console.error('onboarding save failed', err);
      toast.warning('Could not save that. Try again in a moment.');
      setSaving(false);
    }
  };

  const skipAll = () => finishAndLeave(async () => {});

  const nextFromAbout = async () => {
    if (!user || !supabase) return;
    setSaving(true);
    try {
      await saveProfile(supabase, user.id, {
        background: background.trim() || null,
        goal: goal.trim() || null,
      });
      setStep(2);
    } catch (err) {
      console.error('save background failed', err);
      toast.warning('Could not save that. Try again in a moment.');
    } finally {
      setSaving(false);
    }
  };

  const nextFromRound = async () => {
    if (!user || !supabase) return;
    setSaving(true);
    try {
      await saveProfile(supabase, user.id, { target_round: round });
      setStep(3);
    } catch (err) {
      console.error('save round failed', err);
      toast.warning('Could not save that. Try again in a moment.');
    } finally {
      setSaving(false);
    }
  };

  const finish = () =>
    finishAndLeave(async () => {
      if (!user || !supabase) return;
      await saveDocuments(supabase, user.id, { resume, jd, stories });
    });

  // Auth still resolving, or redirecting a guest away: render nothing.
  if (!isSupabaseConfigured || loading || !user) {
    return <div className="min-h-svh" />;
  }

  return (
    <>
      <SideNav />
      <main className="min-h-svh pt-16 md:pt-0 md:pl-60">
        <div className="mx-auto flex min-h-svh w-full max-w-xl flex-col justify-center px-4 py-8 md:py-12">
          <section className="bg-card border-border/60 flex w-full flex-col gap-5 rounded-2xl border px-6 py-8 shadow-sm">
            {step === 0 ? (
              <div className="flex flex-col items-center gap-4 text-center">
                <OwlMascot size={72} />
                <h1 className="text-foreground text-2xl font-semibold tracking-tight">
                  Let&apos;s set you up
                </h1>
                <p className="text-muted-foreground max-w-sm text-sm leading-6">
                  Save your background and documents once, and every practice session reuses them.
                  Three quick steps. Skip anything you like.
                </p>
                <div className="mt-2 flex flex-col items-center gap-3">
                  <Button
                    size="lg"
                    onClick={() => setStep(1)}
                    className="w-56 rounded-full font-mono text-xs font-bold tracking-wider uppercase"
                  >
                    Get started
                  </Button>
                  <button
                    type="button"
                    onClick={skipAll}
                    disabled={saving}
                    className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4 disabled:opacity-50"
                  >
                    Skip for now
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Progress header, shared by the three content steps. */}
                <div className="flex items-center justify-between">
                  <div className="flex flex-col gap-2">
                    <span className="text-primary text-xs font-bold tracking-widest uppercase">
                      Step {step} of {STEPS.length}
                    </span>
                    <div className="flex gap-1.5">
                      {STEPS.map((_, i) => (
                        <span
                          key={i}
                          className={`h-1.5 w-8 rounded-full ${
                            i < step ? 'bg-primary' : 'bg-muted'
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={skipAll}
                    disabled={saving}
                    className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4 disabled:opacity-50"
                  >
                    Skip setup
                  </button>
                </div>

                {step === 1 && (
                  <div className="flex flex-col gap-4">
                    <div>
                      <h2 className="text-foreground text-lg font-semibold">
                        Tell me a bit about you
                      </h2>
                      <p className="text-muted-foreground pt-1 text-sm">
                        A line or two. It helps shape the questions you get and sharpens the
                        coaching.
                      </p>
                    </div>
                    <Field label="Your background">
                      <textarea
                        value={background}
                        onChange={(e) => setBackground(e.target.value)}
                        placeholder="PM, 5 yrs, fintech. Led a payments platform team of 8."
                        rows={3}
                        className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                      />
                    </Field>
                    <Field label="What you're prepping for (optional)">
                      <textarea
                        value={goal}
                        onChange={(e) => setGoal(e.target.value)}
                        placeholder="Series B PM loops; want sharper leadership stories."
                        rows={2}
                        className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                      />
                    </Field>
                    <div className="flex items-center justify-end gap-4 pt-1">
                      <button
                        type="button"
                        onClick={() => setStep(2)}
                        disabled={saving}
                        className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4 disabled:opacity-50"
                      >
                        Skip this step
                      </button>
                      <Button
                        onClick={nextFromAbout}
                        disabled={saving}
                        className="rounded-full font-mono text-xs font-bold tracking-wider uppercase"
                      >
                        {saving ? 'Saving…' : 'Next'}
                      </Button>
                    </div>
                  </div>
                )}

                {step === 2 && (
                  <div className="flex flex-col gap-4">
                    <div>
                      <h2 className="text-foreground text-lg font-semibold">
                        Which round are you practicing for?
                      </h2>
                      <p className="text-muted-foreground pt-1 text-sm">
                        This preselects your round on the New Session form. You can change it any
                        time.
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {ROUNDS.map((r) => (
                        <button
                          key={r}
                          type="button"
                          onClick={() => setRound(r)}
                          className={`rounded-xl border p-3 text-sm font-medium transition-colors ${
                            round === r
                              ? 'border-primary bg-primary/5 text-foreground'
                              : 'border-input text-muted-foreground hover:border-ring/50 hover:text-foreground'
                          }`}
                        >
                          {ROUND_NAMES[r]}
                        </button>
                      ))}
                    </div>
                    <div className="flex items-center justify-between gap-4 pt-1">
                      <button
                        type="button"
                        onClick={() => setStep(1)}
                        disabled={saving}
                        className="text-muted-foreground hover:text-foreground text-sm disabled:opacity-50"
                      >
                        Back
                      </button>
                      <div className="flex items-center gap-4">
                        <button
                          type="button"
                          onClick={() => setStep(3)}
                          disabled={saving}
                          className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4 disabled:opacity-50"
                        >
                          Skip this step
                        </button>
                        <Button
                          onClick={nextFromRound}
                          disabled={saving}
                          className="rounded-full font-mono text-xs font-bold tracking-wider uppercase"
                        >
                          {saving ? 'Saving…' : 'Next'}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {step === 3 && (
                  <div className="flex flex-col gap-4">
                    <div>
                      <h2 className="text-foreground text-lg font-semibold">Add your documents</h2>
                      <p className="text-muted-foreground pt-1 text-sm">
                        Upload once, reuse in every session. These feed your questions, grading, and
                        coach; the live interviewer never sees them.
                      </p>
                    </div>
                    <DocInput
                      label="Resume"
                      value={resume}
                      onChange={setResume}
                      placeholder="Upload a .pdf/.md/.txt or paste your resume text"
                      allowUpload
                    />
                    <DocInput
                      label="Job description (optional)"
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
                    <div className="flex items-center justify-between gap-4 pt-1">
                      <button
                        type="button"
                        onClick={() => setStep(2)}
                        disabled={saving}
                        className="text-muted-foreground hover:text-foreground text-sm disabled:opacity-50"
                      >
                        Back
                      </button>
                      <div className="flex items-center gap-4">
                        <button
                          type="button"
                          onClick={skipAll}
                          disabled={saving}
                          className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4 disabled:opacity-50"
                        >
                          Skip this step
                        </button>
                        <Button
                          onClick={finish}
                          disabled={saving}
                          className="rounded-full font-mono text-xs font-bold tracking-wider uppercase"
                        >
                          {saving ? 'Saving…' : 'Finish'}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </main>
    </>
  );
}
