"""Answer text -> rubric-aligned rewrite notes (spec 5.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.engine.state import RoundProfile
from src.grading.ammo import Doc
from src.llm.client import complete


class RewriteNote(BaseModel):
    dimension: str
    problem: str
    fix: str


class RewriteResult(BaseModel):
    notes: list[RewriteNote] = Field(default_factory=list)
    rewritten_answer: str = ""


def rewrite(question: str, answer: str, round: RoundProfile,
            docs: list[Doc] | None = None) -> RewriteResult:
    docs_block = "\n\n".join(f"[{d.name}]\n{d.text}" for d in (docs or []))
    band = round.length_band_s
    result = complete("answer_rewrite", {
        "question": question,
        "answer": answer,
        "docs": docs_block or "(none supplied)",
        "length_band_low": str(band[0]),
        "length_band_high": str(band[1]),
    }, json_schema={"type": "object"})

    raw = result.parsed or {}
    notes = [RewriteNote(
        dimension=str(n.get("dimension", "")).lower(),
        problem=str(n.get("problem", "")),
        fix=str(n.get("fix", "")))
        for n in raw.get("rewrite_notes", [])]
    return RewriteResult(notes=notes,
                         rewritten_answer=str(raw.get("rewritten_answer", "")))
