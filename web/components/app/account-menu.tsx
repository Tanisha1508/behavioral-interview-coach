'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  ClockCounterClockwiseIcon,
  GoogleLogoIcon,
  SignOutIcon,
} from '@phosphor-icons/react/dist/ssr';
import { useUser } from '@/hooks/useUser';
import { isSupabaseConfigured } from '@/lib/supabase/client';

// The landing gate: signed-out visitors see this instead of the setup
// form (user decision 2026-07-13: setup is visible only after sign-in).
export function SignInCard() {
  const { supabase } = useUser();
  const [busy, setBusy] = useState(false);

  const signIn = async () => {
    if (!supabase) return;
    setBusy(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) {
      setBusy(false);
      console.error('sign-in failed', error);
      toast.warning('Sign-in did not start. Try again in a moment.');
    }
  };

  return (
    <section className="bg-card border-border/60 mx-auto my-6 flex w-full max-w-xl flex-col items-center gap-3 rounded-2xl border px-6 py-10 text-center shadow-sm">
      <h2 className="text-foreground text-lg font-semibold">Sign in to start practicing</h2>
      <p className="text-muted-foreground max-w-sm text-sm leading-6">
        Your sessions, scores, saved documents, and rewrites are kept in your account, so the coach
        remembers where you left off.
      </p>
      <button
        type="button"
        onClick={signIn}
        disabled={busy}
        className="bg-primary text-primary-foreground hover:bg-primary/90 mt-2 flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
      >
        <GoogleLogoIcon weight="bold" className="size-4" />
        {busy ? 'Opening…' : 'Continue with Google'}
      </button>
    </section>
  );
}

// Sign-in / signed-in strip shown on the setup card. Renders nothing when
// Supabase is not configured, so guest-only deployments are unaffected.
export function AccountMenu() {
  const { user, loading, supabase } = useUser();
  const [busy, setBusy] = useState(false);

  if (!isSupabaseConfigured || loading) return null;

  const signIn = async () => {
    if (!supabase) return;
    setBusy(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) {
      setBusy(false);
      console.error('sign-in failed', error);
      toast.warning('Sign-in did not start. Try again in a moment.');
    }
  };

  const signOut = async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    toast.info('Signed out. Sessions will no longer be saved.');
  };

  if (!user) {
    return (
      <div className="border-border/60 flex items-center justify-between gap-2 border-b pb-3">
        <span className="text-muted-foreground text-xs">
          Sign in to save sessions, documents, and rewrites.
        </span>
        <button
          type="button"
          onClick={signIn}
          disabled={busy}
          className="border-input text-foreground hover:border-ring/50 flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
        >
          <GoogleLogoIcon weight="bold" className="size-3.5" />
          {busy ? 'Opening…' : 'Sign in with Google'}
        </button>
      </div>
    );
  }

  const name = (user.user_metadata?.full_name as string) || user.email || 'Signed in';

  return (
    <div className="border-border/60 flex items-center justify-between gap-2 border-b pb-3">
      <span className="text-muted-foreground min-w-0 truncate text-xs">
        Signed in as <span className="text-foreground font-medium">{name}</span>. Sessions are saved
        to your history.
      </span>
      <span className="flex shrink-0 items-center gap-3">
        <Link
          href="/history"
          className="text-primary flex items-center gap-1 text-xs font-medium underline underline-offset-2"
        >
          <ClockCounterClockwiseIcon className="size-3.5" />
          History
        </Link>
        <button
          type="button"
          onClick={signOut}
          className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs underline underline-offset-2 transition-colors"
        >
          <SignOutIcon className="size-3.5" />
          Sign out
        </button>
      </span>
    </div>
  );
}
