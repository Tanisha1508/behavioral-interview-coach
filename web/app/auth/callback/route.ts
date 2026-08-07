import { NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';

// OAuth landing: Google redirects here (via Supabase) with a one-time code
// that gets exchanged for a session cookie.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/';

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      const destination = next.startsWith('/') ? next : '/';
      const separator = destination.includes('?') ? '&' : '?';
      // Sign-in completes server-side (this route), but Amplitude is
      // client-only — the landing page fires the event and strips this
      // param so a refresh never double-counts it.
      return NextResponse.redirect(`${origin}${destination}${separator}signed_in=1`);
    }
  }

  return NextResponse.redirect(`${origin}/?auth_error=1`);
}
