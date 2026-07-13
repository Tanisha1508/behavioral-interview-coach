"""Resume + JD -> tailored question pack (spec 5.2). Done-criterion: every
question maps to a real resume line, enforced by exact substring match here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.engine.state import Question, RoundProfile
from src.llm.client import complete


class PackQuestion(BaseModel):
    text: str
    bucket: str
    resume_line: str
    why_likely: str = ""


class QuestionPack(BaseModel):
    questions: list[PackQuestion] = Field(default_factory=list)
    dropped: int = 0  # items discarded for non-verbatim resume_line

    def as_queue_questions(self) -> list[Question]:
        return [Question(id=f"pack_{i + 1:02d}", text=q.text,
                         expected_buckets=[q.bucket], source="pack")
                for i, q in enumerate(self.questions)]


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def generate_pack(resume_text: str, jd_text: str,
                  round: RoundProfile) -> QuestionPack:
    result = complete("coach_questions", {
        "resume": resume_text,
        "jd": jd_text,
        "profile_id": round.profile_id,
    }, json_schema={"type": "object"})

    resume_norm = _normalize(resume_text)
    kept: list[PackQuestion] = []
    dropped = 0
    for raw in (result.parsed or {}).get("questions", []):
        line = str(raw.get("resume_line", "")).strip()
        if not line or _normalize(line) not in resume_norm:
            dropped += 1
            continue
        kept.append(PackQuestion(
            text=str(raw.get("text", "")).strip(),
            bucket=str(raw.get("bucket", "")).strip().lower(),
            resume_line=line,
            why_likely=str(raw.get("why_likely", "")).strip()))
    return QuestionPack(questions=kept, dropped=dropped)
