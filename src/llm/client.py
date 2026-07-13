"""LLM client (spec 5.2): Gemini primary, Groq failover on 429, daily call
ledger so free caps are never blown silently. Prompts live in
src/llm/prompts/ as files, never inline in code.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
LEDGER_PATH = ROOT / "data" / "llm_ledger.json"


class DailyCapReached(RuntimeError):
    """Raised when the ledger blocks a call. Prescribed action: stop and
    report (docs/FALLBACKS.md), never silently switch providers."""


class LLMUnavailable(RuntimeError):
    """Both Gemini and Groq failed."""


@dataclass
class LLMResult:
    text: str
    parsed: Optional[Any] = None
    provider: str = "gemini"
    failovers: int = 0


@dataclass
class Settings:
    primary_model: str = "gemini-2.5-flash"
    lite_model: str = "gemini-3.1-flash-lite"
    failover_model: str = "llama-3.3-70b-versatile"
    daily_call_cap: int = 200
    temperature: float = 0.4

    @classmethod
    def load(cls) -> "Settings":
        cfg = yaml.safe_load(open(ROOT / "config" / "settings.yaml"))["llm"]
        return cls(
            primary_model=cfg["primary_model"],
            lite_model=cfg.get("lite_model", "gemini-3.1-flash-lite"),
            failover_model=cfg["failover_model"],
            daily_call_cap=int(cfg["daily_call_cap"]),
            temperature=float(cfg["temperature"]),
        )


_settings: Settings | None = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


# ---------- ledger ----------

def _ledger_read() -> dict:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text())
    return {}


def _ledger_bump() -> int:
    today = dt.date.today().isoformat()
    data = _ledger_read()
    data[today] = data.get(today, 0) + 1
    LEDGER_PATH.parent.mkdir(exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(data))
    return data[today]


def calls_today() -> int:
    return _ledger_read().get(dt.date.today().isoformat(), 0)


# ---------- prompts ----------

def load_prompt(prompt_id: str, vars: dict[str, str]) -> str:
    path = PROMPTS_DIR / f"{prompt_id}.txt"
    template = path.read_text()
    for key, value in vars.items():
        template = template.replace("{" + key + "}", str(value))
    return template


# ---------- providers ----------

def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "rate limit" in text.lower()


def _is_transient(exc: Exception) -> bool:
    text = str(exc)
    return any(code in text for code in ("503", "500", "502", "504",
                                         "UNAVAILABLE", "DEADLINE_EXCEEDED"))


def _call_gemini(prompt: str, json_schema: dict | None,
                 model: str | None = None) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    config: dict[str, Any] = {"temperature": settings().temperature}
    if json_schema is not None:
        # JSON mode only; the schema itself is stated in the prompt. Typed
        # response_schema objects are stricter than free-tier flash needs.
        config["response_mime_type"] = "application/json"
    response = client.models.generate_content(
        model=model or settings().primary_model,
        contents=prompt,
        config=types.GenerateContentConfig(**config),
    )
    return response.text or ""


def _call_groq(prompt: str, json_schema: dict | None) -> str:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    kwargs: dict[str, Any] = {"temperature": settings().temperature}
    if json_schema is not None:
        kwargs["response_format"] = {"type": "json_object"}
        prompt += ("\n\nReturn ONLY a JSON object matching this schema:\n"
                   + json.dumps(json_schema))
    response = client.chat.completions.create(
        model=settings().failover_model,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return response.choices[0].message.content or ""


# ---------- public API ----------

_failover_log: list[str] = []


def complete(prompt_id: str, vars: dict[str, str],
             json_schema: dict | None = None) -> LLMResult:
    prompt = load_prompt(prompt_id, vars)

    text = None
    provider, failovers = "gemini", 0
    last_exc: Exception | None = None

    # The ledger caps Gemini attempts only (verified free tier: 20/day).
    # At the cap we route straight to the Groq failover instead of burning
    # attempts that will 429; we never silently drop the turn.
    if calls_today() < settings().daily_call_cap:
        _ledger_bump()
        for attempt in range(3):
            try:
                text = _call_gemini(prompt, json_schema)
                break
            except Exception as gemini_exc:
                last_exc = gemini_exc
                if _is_transient(gemini_exc) and attempt < 2:
                    time.sleep(2 * (attempt + 1))  # backoff then retry Gemini
                    continue
                if not (_is_rate_limit(gemini_exc) or _is_transient(gemini_exc)):
                    raise
                break
    else:
        last_exc = DailyCapReached(
            f"ledger cap {settings().daily_call_cap} reached "
            f"({calls_today()} Gemini calls today)")

    if (text is None and settings().lite_model
            and os.environ.get("GOOGLE_API_KEY")):
        # Gemini quotas are per model: flash-lite has its own free-tier
        # pool, so it absorbs flash exhaustion before we lean on Groq
        # (added 2026-07-12 after both flash and Groq 429'd mid-test).
        # The ledger cap guards flash only; lite always gets its chance
        # (live 2026-07-12: the capped ledger skipped a healthy lite tier
        # while Groq was empty, killing scoring for no reason).
        _failover_log.append(f"{time.time()}: gemini failed on {prompt_id}: {last_exc}")
        try:
            text = _call_gemini(prompt, json_schema, model=settings().lite_model)
            provider, failovers = "gemini-lite", 1
        except Exception as lite_exc:
            _failover_log.append(
                f"{time.time()}: gemini-lite failed on {prompt_id}: {lite_exc}")
            if not (_is_rate_limit(lite_exc) or _is_transient(lite_exc)):
                raise
            if not isinstance(last_exc, DailyCapReached):
                # Keep the cap as the headline error when it applies.
                last_exc = lite_exc

    if text is None:
        # Rate-limited, capped, or persistently unavailable: fail over to
        # Groq (docs/FALLBACKS.md), never drop the turn.
        _failover_log.append(f"{time.time()}: gemini failed on {prompt_id}: {last_exc}")
        if not os.environ.get("GROQ_API_KEY"):
            if isinstance(last_exc, DailyCapReached):
                raise last_exc
            raise LLMUnavailable(
                f"gemini failed ({last_exc}) and no GROQ_API_KEY is set")
        try:
            text = _call_groq(prompt, json_schema)
            provider, failovers = "groq", 1
        except Exception as groq_exc:
            if isinstance(last_exc, DailyCapReached):
                raise DailyCapReached(
                    f"{last_exc} and groq failed: {groq_exc}") from groq_exc
            raise LLMUnavailable(
                f"gemini failed ({last_exc}) and groq failed: {groq_exc}"
            ) from groq_exc

    parsed = None
    if json_schema is not None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned[4:] if cleaned.startswith("json") else cleaned
        parsed = json.loads(cleaned)
    return LLMResult(text=text, parsed=parsed, provider=provider,
                     failovers=failovers)
