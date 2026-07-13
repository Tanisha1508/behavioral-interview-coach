"""Supabase persistence (scope item 15): sessions + answers rows over REST.

Active only when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set and the
participant carried a user_id attribute (a signed-in web user). Everything
else, guests included, keeps the local JSON record in data/sessions as the
only store. Every network call swallows its own errors: persistence must
never take down a live session.

The service role key bypasses RLS, so user_id is written explicitly here;
browser reads go through the anon key where RLS scopes rows to the user.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("interview-coach.cloud")

TIMEOUT_S = 6.0


def _config() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None
    return url, key


def user_id_from_room(room) -> str | None:
    """The Supabase user id the web token route put in participant
    attributes; None for guests, console mode, and unit tests."""
    if room is None:
        return None
    try:
        for participant in room.remote_participants.values():
            uid = (participant.attributes or {}).get("user_id", "").strip()
            if uid:
                return uid
    except Exception:
        logger.exception("could not read participant attributes")
    return None


class CloudSession:
    """One sessions row plus its answers rows, created lazily on first
    write so an aborted setup never leaves an empty row behind."""

    def __init__(self, user_id: str, session_type: str,
                 round_id: str | None, base_url: str, key: str):
        self.user_id = user_id
        self.session_type = session_type
        self.round_id = round_id
        self._rest = f"{base_url}/rest/v1"
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._session_id: str | None = None
        self._last_answer_id: str | None = None
        self._started = time.monotonic()
        self._finished = False

    @staticmethod
    def create_if_configured(room, session_type: str,
                             round_id: str | None) -> "CloudSession | None":
        cfg = _config()
        user_id = user_id_from_room(room)
        if cfg is None or user_id is None:
            return None
        logger.info("cloud persistence on: %s session for user %s",
                    session_type, user_id)
        return CloudSession(user_id, session_type, round_id, *cfg)

    # ---- internals ----

    async def _post(self, table: str, payload: dict) -> dict | None:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(f"{self._rest}/{table}",
                                     headers=self._headers, json=payload)
            resp.raise_for_status()
            rows = resp.json()
            return rows[0] if rows else None

    async def _patch(self, table: str, row_id: str, payload: dict) -> None:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.patch(
                f"{self._rest}/{table}?id=eq.{row_id}",
                headers=self._headers, json=payload)
            resp.raise_for_status()

    async def _ensure_session(self) -> str | None:
        if self._session_id is not None:
            return self._session_id
        row = await self._post("sessions", {
            "user_id": self.user_id,
            "type": self.session_type,
            "round": self.round_id,
        })
        self._session_id = row["id"] if row else None
        return self._session_id

    # ---- write points, all safe to call unconditionally ----

    async def record_answer(self, *, question: str, transcript: str,
                            duration_s: float | None,
                            scores: dict | None,
                            rewrite: str | None = None) -> None:
        try:
            session_id = await self._ensure_session()
            if session_id is None:
                return
            row = await self._post("answers", {
                "session_id": session_id,
                "user_id": self.user_id,
                "question": question,
                "transcript": transcript,
                "duration_s": int(duration_s) if duration_s else None,
                "scores": scores,
                "rewrite": rewrite,
            })
            self._last_answer_id = row["id"] if row else None
        except Exception:
            logger.exception("cloud answer write failed (session continues)")

    async def attach_rewrite(self, rewrite: str) -> None:
        if not self._last_answer_id:
            return
        try:
            await self._patch("answers", self._last_answer_id,
                              {"rewrite": rewrite})
        except Exception:
            logger.exception("cloud rewrite write failed (session continues)")

    async def finish(self, *, dropped: int = 0,
                     patterns: Any = None, raw: dict | None = None) -> None:
        if self._finished or self._session_id is None:
            # No answers were written: nothing worth a history row.
            return
        self._finished = True
        try:
            await self._patch("sessions", self._session_id, {
                "duration_s": int(time.monotonic() - self._started),
                "dropped": dropped,
                "patterns": patterns,
                "raw": raw,
            })
        except Exception:
            logger.exception("cloud session finish failed")
