# Runbook: deploy + accounts (scope items 12 and 15)

Written 2026-07-13. This is the execution script for hosting the app and adding
user accounts. It is deliberately mechanical: a later session (any model) should
be able to follow it step by step without re-deciding anything. Decisions behind
it are logged in DECISIONS.md under 2026-07-13.

Free-tier facts verified 2026-07-13:
- LiveKit Cloud Build plan (free): 1 agent deployment, 5 concurrent agent
  sessions, 1,000 agent session minutes/month, no credit card. Enough for a
  portfolio demo. Project already exists: voiceagent1 (India South).
- Vercel Hobby (free): hosts the Next.js app including the /api/token route.
- Supabase free: auth (Google sign-in), 500 MB Postgres, plenty.

Credentials rule (binding): no secret ever goes into code or chat. Everything
lands in .env locally and in each host's environment settings.

## Phase A — hosted baseline (item 12, no accounts yet)

### A1. Frontend to Vercel
1. User signs in at vercel.com with Google (tanishag1508@gmail.com), Hobby plan.
2. The repo is not on git. Two options; pick one:
   - Preferred: create a GitHub repo (private is fine), push the project, then
     Vercel -> Add New Project -> import the repo, set Root Directory to `web`.
   - No-GitHub alternative: `npm i -g vercel` then from `web/` run `vercel`
     (CLI login, deploys directly). Redeploys are `vercel --prod`.
3. Environment variables in Vercel (Project -> Settings -> Environment Variables),
   copied from `web/.env.local`:
   - LIVEKIT_URL (wss://voiceagent1-2fwjmm6w.livekit.cloud)
   - LIVEKIT_API_KEY
   - LIVEKIT_API_SECRET
4. Deploy, open the vercel.app URL, confirm the setup form renders.

### A2. Agent worker to LiveKit Cloud
1. Install the CLI: `brew install livekit-cli` (gives the `lk` command).
2. `lk cloud auth` (opens browser; pick project voiceagent1).
3. Create `Dockerfile` at repo root (agent hosting runs containers):
   ```
   FROM python:3.12-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY src ./src
   COPY config ./config
   RUN python -m src.agent download-files || true
   CMD ["python", "-m", "src.agent", "start"]
   ```
   Note: `download-files` pre-bakes model weights (Silero VAD, turn detector)
   into the image so cold starts do not download them.
4. `lk agent create` from the repo root (generates livekit.toml, builds, deploys).
5. Secrets to set on the agent (CLI prompts, or `lk agent update-secrets`):
   GOOGLE_API_KEY, DEEPGRAM_API_KEY, ELEVEN_API_KEY, GROQ_API_KEY
   (exactly the keys in the root `.env`; LIVEKIT_* are injected automatically).
6. Stop the local worker first (`pkill -f "src.agent dev"`) or two workers will
   compete for jobs. To go back to local dev later, stop the cloud agent from
   the dashboard or run the local worker with a different agent name.
7. Verify: hosted URL -> start a 1-question Drill -> full loop works.

Phase A done-criterion (item 12): a stranger with the vercel.app link can run a
graded Drill rep end to end with no local process running.

## Phase B — Supabase project + schema (item 15 groundwork)

1. User signs in at supabase.com with Google, creates project `interview-coach`,
   free plan, region Mumbai.
2. SQL Editor -> paste `supabase/schema.sql` (in this repo) -> Run.
3. Enable Google sign-in: Authentication -> Providers -> Google. This needs a
   Google Cloud OAuth client (console.cloud.google.com -> APIs & Services ->
   Credentials -> Create OAuth client ID -> Web application). Authorized
   redirect URI is shown by Supabase on that same provider page (copy it
   exactly). Put the client ID and secret into the Supabase provider form.
   Also add the vercel.app domain and http://localhost:3000 under
   Authentication -> URL Configuration (Site URL + redirect URLs).
4. Keys (Project Settings -> API):
   - Project URL + anon public key -> `web/.env.local` as
     NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY, and the same two
     in Vercel env settings.
   - service_role key -> root `.env` as SUPABASE_SERVICE_ROLE_KEY and into the
     LiveKit agent secrets. Never into the web app.

## Phase C — code wiring (item 15 implementation, in this order)

Each step is a checkpoint: build, run, verify, update PROGRESS.md.

1. **Web auth.** `npm install @supabase/supabase-js @supabase/ssr` (the one
   allowed new dependency). Login page with "Continue with Google", session
   cookie via @supabase/ssr middleware, sign-out in a small account menu.
   Unauthenticated users can still use the app (guest mode); auth unlocks
   saving. Guest mode keeps the demo link frictionless for recruiters.
2. **Token route identity.** /api/token: if a Supabase session cookie exists,
   set the LiveKit participant identity to the Supabase user id and put
   `{"user_id": ...}` in participant attributes. Guests keep a random identity.
3. **Agent persistence.** In `save_session`: when SUPABASE_URL +
   SUPABASE_SERVICE_ROLE_KEY are set and the participant carried a user_id,
   also insert into `sessions` + `answers` (plain httpx POST to the Supabase
   REST endpoint; no new SDK needed). Local JSON stays as-is (it is the debug
   record and the fallback when env or user_id is absent).
4. **Saved documents.** On the setup form, for signed-in users: load saved
   docs on mount (prefill), "Save to my account" writes upserts to `documents`.
5. **Save buttons.** Score card rewrite panel and coach gap list get a save
   action -> `saved_items`. Toast on success.
6. **History page.** /history: session list (date, type, round, score summary),
   expandable to per-answer scores, transcript, rewrite. Data comes from
   Supabase client-side with the anon key (RLS scopes it to the user).
7. **Design pass (item 13)** then hosted verification + README (item 14).

## Watch items
- LiveKit free plan is hard-capped (1,000 agent min/month); when exhausted the
  demo stops until the month rolls over. Fine for portfolio use.
- ElevenLabs quota still exhausted; Deepgram Aura carries TTS (already wired).
- data/sessions/*.json on the hosted worker is ephemeral; after Phase C step 3
  the durable record is Supabase.
