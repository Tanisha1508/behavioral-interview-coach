"""Missed ammo (spec 5.2): facts in the user's own docs that the spoken
answer left out. Every flagged fact must be an exact substring of the source
doc; anything else is discarded here in code, never shipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from src.llm.client import complete


@dataclass
class Doc:
    name: str  # "resume" | "jd" | "stories" | free label
    text: str


class AmmoItem(BaseModel):
    fact: str
    doc_source: str
    relevance: str = ""
    absent_from_answer: bool = True


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def missed_ammo(transcript: str, user_docs: list[Doc],
                question: str = "") -> list[AmmoItem]:
    if not user_docs:
        return []

    docs_block = "\n\n".join(f"[{d.name}]\n{d.text}" for d in user_docs)
    result = complete("missed_ammo", {
        "docs": docs_block,
        "transcript": transcript,
        "question": question or "(not recorded)",
    }, json_schema={"type": "object"})

    doc_norms = {d.name: _normalize(d.text) for d in user_docs}
    all_docs_norm = _normalize(docs_block)
    transcript_norm = _normalize(transcript)

    items: list[AmmoItem] = []
    for raw in (result.parsed or {}).get("items", []):
        fact = str(raw.get("fact", "")).strip()
        if not fact:
            continue
        fact_norm = _normalize(fact)
        source = str(raw.get("doc_source", "")).strip()
        # Hard rule: exact substring of the named doc, or of any doc if the
        # source label is off. Hallucinated items are dropped, not repaired.
        if fact_norm not in doc_norms.get(source, ""):
            matches = [n for n, t in doc_norms.items() if fact_norm in t]
            if not matches:
                continue
            source = matches[0]
        # Must actually be absent from the spoken answer.
        if fact_norm in transcript_norm:
            continue
        items.append(AmmoItem(fact=fact, doc_source=source,
                              relevance=str(raw.get("relevance", ""))))
    return items
