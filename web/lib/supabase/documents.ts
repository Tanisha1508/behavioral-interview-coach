import type { SupabaseClient } from '@supabase/supabase-js';

// Saved setup documents (documents table, RLS-scoped to the user).
// One row per kind, upserted on save.
export const DOC_KINDS = ['resume', 'jd', 'stories', 'bio'] as const;
export type DocKind = (typeof DOC_KINDS)[number];
export type SavedDocs = Partial<Record<DocKind, string>>;

export async function loadDocuments(supabase: SupabaseClient): Promise<SavedDocs> {
  const { data, error } = await supabase.from('documents').select('kind, content');
  if (error) throw error;
  const docs: SavedDocs = {};
  for (const row of data ?? []) {
    if ((DOC_KINDS as readonly string[]).includes(row.kind)) {
      docs[row.kind as DocKind] = row.content;
    }
  }
  return docs;
}

export async function saveDocuments(
  supabase: SupabaseClient,
  userId: string,
  docs: SavedDocs
): Promise<number> {
  const rows = Object.entries(docs)
    .filter(([, content]) => content && content.trim())
    .map(([kind, content]) => ({
      user_id: userId,
      kind,
      content: content as string,
      updated_at: new Date().toISOString(),
    }));
  if (!rows.length) return 0;
  const { error } = await supabase.from('documents').upsert(rows, {
    onConflict: 'user_id,kind',
  });
  if (error) throw error;
  return rows.length;
}
