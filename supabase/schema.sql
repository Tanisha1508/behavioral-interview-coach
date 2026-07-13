-- Behavioral Interview Coach: accounts + history schema (scope item 15).
-- Run this once in the Supabase SQL editor (Dashboard -> SQL Editor -> New query -> paste -> Run).
-- Safe to re-run: everything is IF NOT EXISTS / OR REPLACE.

-- Saved documents: one row per user per kind, upserted on save.
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('resume', 'jd', 'stories', 'bio')),
  content text not null,
  updated_at timestamptz not null default now(),
  unique (user_id, kind)
);

-- Activity log: one row per completed session.
-- raw holds the full session record the agent already builds today
-- (the same JSON that data/sessions/*.json holds), so nothing is lost.
create table if not exists public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  type text not null check (type in ('drill', 'simulation', 'coach')),
  round text,
  started_at timestamptz not null default now(),
  duration_s integer,
  dropped integer not null default 0,
  patterns jsonb,
  raw jsonb
);

-- One row per question answered inside a session (drill rep or simulation rep).
create table if not exists public.answers (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  question text not null,
  transcript text,
  duration_s integer,
  scores jsonb, -- the 6-dimension rubric result; null when the grader was unavailable
  rewrite text, -- filled when the user requested a rewrite for this answer
  created_at timestamptz not null default now()
);

-- Things the user chose to keep: a good rewrite, a full answer worth reusing,
-- or a gap the coach flagged.
create table if not exists public.saved_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('rewrite', 'answer', 'gap')),
  title text,
  content text not null,
  source_session_id uuid references public.sessions (id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists sessions_user_started_idx on public.sessions (user_id, started_at desc);
create index if not exists answers_session_idx on public.answers (session_id);
create index if not exists saved_items_user_idx on public.saved_items (user_id, created_at desc);

-- Row level security: every table is user-private. The browser uses the anon
-- key and only ever sees auth.uid() = user_id rows. The agent worker uses the
-- service role key, which bypasses RLS, to write sessions and answers.
alter table public.documents enable row level security;
alter table public.sessions enable row level security;
alter table public.answers enable row level security;
alter table public.saved_items enable row level security;

drop policy if exists "own documents" on public.documents;
create policy "own documents" on public.documents
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own sessions" on public.sessions;
create policy "own sessions" on public.sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own answers" on public.answers;
create policy "own answers" on public.answers
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own saved items" on public.saved_items;
create policy "own saved items" on public.saved_items
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
