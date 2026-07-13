'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
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
  saveProfile,
} from '@/lib/supabase/profiles';

export default function ProfilePage() {
  const { user, loading, supabase } = useUser();
  const [background, setBackground] = useState('');
  const [goal, setGoal] = useState('');
  const [round, setRound] = useState<TargetRound | ''>('');
  const [resume, setResume] = useState('');
  const [jd, setJd] = useState('');
  const [stories, setStories] = useState('');
  const [bio, setBio] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user || !supabase || loaded) return;
    Promise.all([loadProfile(supabase), loadDocuments(supabase)])
      .then(([p, d]) => {
        if (p?.background) setBackground(p.background);
        if (p?.goal) setGoal(p.goal);
        if (p?.target_round) setRound(p.target_round);
        if (d.resume) setResume(d.resume);
        if (d.jd) setJd(d.jd);
        if (d.stories) setStories(d.stories);
        if (d.bio) setBio(d.bio);
      })
      .catch((err) => console.error('load profile failed', err))
      .finally(() => setLoaded(true));
  }, [user, supabase, loaded]);

  const save = async () => {
    if (!user || !supabase) return;
    setSaving(true);
    try {
      await saveProfile(supabase, user.id, {
        background: background.trim() || null,
        goal: goal.trim() || null,
        target_round: round || null,
      });
      await saveDocuments(supabase, user.id, { resume, jd, stories, bio });
      toast.success('Profile saved.');
    } catch (err) {
      console.error('save profile failed', err);
      toast.warning('Could not save your profile. Try again in a moment.');
    } finally {
      setSaving(false);
    }
  };

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
                Profile
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
                Your profile needs an account. Go back and sign in with Google to save your
                background, round, and documents.
              </p>
            </div>
          ) : loading || !loaded ? (
            <p className="text-muted-foreground mt-6 text-sm">Loading your profile…</p>
          ) : (
            <section className="bg-card border-border/60 mt-6 flex w-full flex-col gap-5 rounded-2xl border px-6 py-8 shadow-sm">
              <Field label="Your background">
                <textarea
                  value={background}
                  onChange={(e) => setBackground(e.target.value)}
                  placeholder="PM, 5 yrs, fintech. Led a payments platform team of 8."
                  rows={3}
                  className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                />
              </Field>
              <Field label="What you're prepping for">
                <textarea
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder="Series B PM loops; want sharper leadership stories."
                  rows={2}
                  className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                />
              </Field>
              <Field label="Default round">
                <select
                  value={round}
                  onChange={(e) => setRound(e.target.value as TargetRound | '')}
                  className="border-input bg-background text-foreground rounded-md border p-2 text-sm"
                >
                  <option value="">No default</option>
                  {ROUNDS.map((r) => (
                    <option key={r} value={r}>
                      {ROUND_NAMES[r]}
                    </option>
                  ))}
                </select>
              </Field>

              <div className="border-border/60 flex flex-col gap-3 border-t pt-5">
                <p className="text-muted-foreground text-xs">
                  Documents feed your questions, grading, and coach; the live interviewer never sees
                  them.
                </p>
                <DocInput
                  label="Resume"
                  value={resume}
                  onChange={setResume}
                  placeholder="Upload a .pdf/.md/.txt or paste your resume text"
                  allowUpload
                />
                <DocInput
                  label="Job description"
                  value={jd}
                  onChange={setJd}
                  placeholder="Upload or paste the JD you are targeting"
                  allowUpload
                />
                <DocInput
                  label="Stories / brag doc"
                  value={stories}
                  onChange={setStories}
                  placeholder="Upload or paste story notes or a brag doc"
                  allowUpload
                />
                <DocInput
                  label="Interviewer bio: shapes the interviewer's style and voice"
                  value={bio}
                  onChange={setBio}
                  placeholder="Paste the interviewer's LinkedIn About text or a short bio"
                  allowUpload
                />
              </div>

              <Button
                size="lg"
                onClick={save}
                disabled={saving}
                className="mt-1 w-full rounded-full font-mono text-xs font-bold tracking-wider uppercase disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save changes'}
              </Button>
            </section>
          )}
        </div>
      </main>
    </>
  );
}
