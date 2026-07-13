'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { useUser } from '@/hooks/useUser';

// "Save to my account" for rewrites, answers, and coach gaps
// (saved_items table). Renders nothing for guests, so every placement is
// safe in guest mode.
export function SaveItemButton({
  kind,
  title,
  content,
  label = 'Save to my account',
  className = 'border-input text-foreground shrink-0 rounded-md border px-2 py-1 text-[11px] disabled:opacity-60',
}: {
  kind: 'rewrite' | 'answer' | 'gap';
  title: string;
  content: string;
  label?: string;
  className?: string;
}) {
  const { user, supabase } = useUser();
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle');

  if (!user || !supabase || !content.trim()) return null;

  const save = async () => {
    setState('saving');
    const { error } = await supabase.from('saved_items').insert({
      user_id: user.id,
      kind,
      title,
      content,
    });
    if (error) {
      console.error('saving item failed', error);
      setState('idle');
      toast.warning('Could not save that. Try again in a moment.');
      return;
    }
    setState('saved');
    toast.success('Saved. Find it on your history page.');
  };

  return (
    <button type="button" onClick={save} disabled={state !== 'idle'} className={className}>
      {state === 'saved' ? 'Saved ✓' : state === 'saving' ? 'Saving…' : label}
    </button>
  );
}
