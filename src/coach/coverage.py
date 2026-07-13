"""Stories vs question set -> coverage map with gaps flagged (spec 5.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.coach.questions import QuestionPack
from src.llm.client import complete

STRENGTHS = {"STRONG", "PARTIAL", "GAP"}


class CoverageEntry(BaseModel):
    question: str
    covered_by: str = ""
    strength: str = "GAP"
    note: str = ""


class CoverageReport(BaseModel):
    entries: list[CoverageEntry] = Field(default_factory=list)

    @property
    def gaps(self) -> list[CoverageEntry]:
        return [e for e in self.entries if e.strength == "GAP"]


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def coverage_map(stories_doc: str, questions: QuestionPack) -> CoverageReport:
    question_lines = "\n".join(
        f"{i + 1}. {q.text}" for i, q in enumerate(questions.questions))
    result = complete("coverage_map", {
        "stories": stories_doc,
        "questions": question_lines,
    }, json_schema={"type": "object"})

    stories_norm = _normalize(stories_doc)
    entries = []
    for raw in (result.parsed or {}).get("coverage", []):
        strength = str(raw.get("strength", "GAP")).upper()
        if strength not in STRENGTHS:
            strength = "GAP"
        covered_by = str(raw.get("covered_by", "")).strip()
        # covered_by must be verbatim from the stories doc; a claimed cover
        # that is not really there downgrades to GAP rather than shipping.
        if covered_by and _normalize(covered_by) not in stories_norm:
            covered_by = ""
            strength = "GAP"
        if not covered_by and strength != "GAP":
            strength = "GAP"
        entries.append(CoverageEntry(
            question=str(raw.get("question", "")).strip(),
            covered_by=covered_by, strength=strength,
            note=str(raw.get("note", "")).strip()))
    return CoverageReport(entries=entries)
