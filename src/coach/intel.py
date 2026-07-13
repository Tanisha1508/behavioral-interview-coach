"""Pasted intel -> extracted questions, temporary bank (spec 5.2)."""

from __future__ import annotations

from src.engine.state import Question
from src.llm.client import complete


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def extract_questions(pasted_text: str) -> list[Question]:
    if not pasted_text.strip():
        return []
    result = complete("intel_extract", {"pasted_text": pasted_text},
                      json_schema={"type": "object"})
    pasted_norm = _normalize(pasted_text)
    out: list[Question] = []
    for i, raw in enumerate((result.parsed or {}).get("questions", [])):
        evidence = str(raw.get("evidence", "")).strip()
        if not evidence or _normalize(evidence) not in pasted_norm:
            continue  # no verbatim evidence, no question (anti-invention rule)
        text = str(raw.get("text", "")).strip()
        if text:
            out.append(Question(id=f"intel_{i + 1:02d}", text=text,
                                source="intel"))
    return out
