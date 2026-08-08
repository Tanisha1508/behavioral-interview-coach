'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import * as amplitude from '@amplitude/analytics-browser';
import { useUser } from '@/hooks/useUser';
import { initAmplitude } from '@/lib/amplitude/client';

// Mounted once in the root layout so every page (not just "/") calls
// initAmplitude() before any track() call elsewhere in the app can fire.
function SignedInTrackerInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useUser();

  useEffect(() => {
    initAmplitude();
    if (searchParams.get('signed_in') !== '1') return;
    amplitude.track('Signed In');

    const params = new URLSearchParams(searchParams);
    params.delete('signed_in');
    const query = params.toString();
    router.replace(query ? `?${query}` : window.location.pathname, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Ties every subsequent web event to the same identity the agent side
  // uses (the Supabase user id), via user_id_from_room in cloud_store.py.
  // Without this, web events (Started Session, Saved Document, ...) and
  // agent events (session_started, answer_graded, ...) for the same real
  // session are two disconnected identities in Amplitude, and any funnel
  // or user-timeline view spanning both silently fails to connect them.
  useEffect(() => {
    if (user) amplitude.setUserId(user.id);
  }, [user]);

  return null;
}

// useSearchParams needs a Suspense boundary in the App Router; this
// component renders nothing, so a null fallback is exact, not a placeholder.
export function SignedInTracker() {
  return (
    <Suspense fallback={null}>
      <SignedInTrackerInner />
    </Suspense>
  );
}
