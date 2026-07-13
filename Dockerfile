# Agent worker image for LiveKit Cloud agent hosting (RUNBOOK-DEPLOY.md A2).
# Built remotely by `lk agent create` / `lk agent deploy`; no local Docker needed.
FROM python:3.12-slim

# ffmpeg: audio resampling used by some plugins; git: pip VCS deps if any.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-agent.txt .
RUN pip install --no-cache-dir -r requirements-agent.txt

COPY src ./src
COPY config ./config
# Runtime writes (session records, llm ledger) land in ./data; ephemeral on
# cloud hosting, which is fine until item 15 moves the durable copy to Supabase.
RUN mkdir -p data/sessions

# Pre-bake model weights (Silero VAD, turn detector) so cold starts do not
# download them. Allowed to fail: the worker also downloads at runtime.
RUN python -m src.agent download-files || true

CMD ["python", "-m", "src.agent", "start"]
