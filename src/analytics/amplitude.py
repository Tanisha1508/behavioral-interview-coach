"""Amplitude server-side event tracking (scope item 16, checkpoint 2).

Covers what only exists in this Python agent process: session engagement,
grading/hallucination-rate signal, and STT/TTS pipeline metrics. Sent to the
same Amplitude project the web client (web/lib/amplitude/client.ts) uses, so
device_id here matches the LiveKit room name the web side never sees but
which ties every event in one session together.

Active only when AMPLITUDE_API_KEY is set. Every call swallows its own
errors: analytics must never take down a live session, same rule as
src/session/cloud_store.py.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("interview-coach.analytics")

TIMEOUT_S = 5.0
INGEST_URL = "https://api2.amplitude.com/2/httpapi"
MIN_ID_LENGTH = 5  # Amplitude drops shorter device_id/user_id values.


def _api_key() -> str | None:
    key = os.environ.get("AMPLITUDE_API_KEY", "").strip()
    return key or None


def device_id_from_room(room) -> str:
    """Every session gets a device_id, guest or signed-in, so engagement
    counts include guest usage (matches the web client's Viewed Home Page,
    which also fires pre-sign-in). Falls back to a padded id below
    Amplitude's minimum length (console mode's room name can be short)."""
    name = (getattr(room, "name", "") or "").strip()
    if len(name) >= MIN_ID_LENGTH:
        return name
    return f"agent-{name or 'unknown'}"


async def track(event_type: str, *, device_id: str,
                user_id: str | None = None,
                event_properties: dict[str, Any] | None = None) -> None:
    """Fire-and-forget: safe to await directly or wrap in
    asyncio.create_task(...) from a hot path that cannot afford the round
    trip. Never raises."""
    key = _api_key()
    if key is None:
        return
    event: dict[str, Any] = {
        "event_type": event_type,
        "device_id": device_id,
        "time": int(time.time() * 1000),
        "event_properties": event_properties or {},
    }
    if user_id and len(user_id) >= MIN_ID_LENGTH:
        event["user_id"] = user_id
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(
                INGEST_URL, json={"api_key": key, "events": [event]})
            resp.raise_for_status()
    except Exception:
        logger.exception("amplitude event %s failed to send", event_type)


def track_sync(event_type: str, *, device_id: str,
               user_id: str | None = None,
               event_properties: dict[str, Any] | None = None) -> None:
    """Synchronous counterpart to track(), for callers with no running event
    loop to await into (e.g. src/llm/client.py's complete(), which always
    runs inside asyncio.to_thread on a worker thread). Same never-raises
    contract."""
    key = _api_key()
    if key is None:
        return
    event: dict[str, Any] = {
        "event_type": event_type,
        "device_id": device_id,
        "time": int(time.time() * 1000),
        "event_properties": event_properties or {},
    }
    if user_id and len(user_id) >= MIN_ID_LENGTH:
        event["user_id"] = user_id
    try:
        with httpx.Client(timeout=TIMEOUT_S) as client:
            resp = client.post(
                INGEST_URL, json={"api_key": key, "events": [event]})
            resp.raise_for_status()
    except Exception:
        logger.exception("amplitude event %s failed to send", event_type)
