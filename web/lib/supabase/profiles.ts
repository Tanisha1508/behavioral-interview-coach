import type { SupabaseClient } from '@supabase/supabase-js';

// User profile (profiles table, RLS-scoped to the user). One row per user.
// Every field is optional: the onboarding wizard is skippable at every step.
// background and goal feed question generation, the grader, and the coach,
// the same channel the documents flow through; the live interviewer never
// sees them. target_round preselects the round on the New Session form.
export const ROUNDS = ['pm', 'consulting', 'mba_admissions', 'tech', 'others'] as const;
export type TargetRound = (typeof ROUNDS)[number];

export const ROUND_NAMES: Record<TargetRound, string> = {
  pm: 'Product Management',
  consulting: 'Consulting',
  mba_admissions: 'MBA Admissions',
  tech: 'Tech',
  others: 'Others',
};

export interface Profile {
  background: string | null;
  goal: string | null;
  target_round: TargetRound | null;
  onboarded_at: string | null;
}

// Returns null when the user has no profile row yet (wizard not seen).
export async function loadProfile(supabase: SupabaseClient): Promise<Profile | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('background, goal, target_round, onboarded_at')
    .maybeSingle();
  if (error) throw error;
  return (data as Profile) ?? null;
}

// Upsert a subset of profile fields. Columns not passed are left untouched on
// an existing row and default to null on a new one, so this is safe to call
// from any single wizard step.
export async function saveProfile(
  supabase: SupabaseClient,
  userId: string,
  fields: Partial<Profile>
): Promise<void> {
  const { error } = await supabase
    .from('profiles')
    .upsert(
      { user_id: userId, ...fields, updated_at: new Date().toISOString() },
      { onConflict: 'user_id' }
    );
  if (error) throw error;
}

// Stamp onboarded_at so the wizard never shows again, preserving whatever
// fields were captured. Called when the wizard is finished OR skipped.
export async function markOnboarded(supabase: SupabaseClient, userId: string): Promise<void> {
  await saveProfile(supabase, userId, { onboarded_at: new Date().toISOString() });
}
