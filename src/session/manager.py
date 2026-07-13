"""Session orchestration and the context partition wall (spec 5.3).

This is the only module that assembles LLM contexts. The rule it enforces:

  Interviewer (live)  -> question + persona + live transcript. NEVER the
                         user's resume, JD, stories, or any pasted doc.
  Grader              -> transcript + probe log + rubric + any docs the
                         user supplied this session.
  Coach               -> any docs the user supplied this session.

The wall is structural: InterviewerContext has no field that could carry a
doc, and the interviewer prompt builder only accepts an InterviewerContext.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.engine.state import (
    AnswerState,
    PersonaParams,
    ProbeRecord,
    Question,
    RoundProfile,
)
from src.grading.ammo import Doc
from src.llm.client import load_prompt
from src.session.setup import SessionConfig

# Doc names the interviewer must never see. "bio" is persona input, consumed
# by extraction before the session; it never enters live context either.
USER_DOC_KEYS = ("resume", "jd", "stories", "bio")

INTENSITY_DESCRIPTORS = {
    1: "gentle: give latitude and rarely push",
    2: "mild: push politely when something is clearly missing",
    3: "firm: press once on weak claims",
    4: "sharp: press hard on weak claims and re-ask when deflected",
    5: "relentless: challenge every unsupported claim",
}


class InterviewerContext(BaseModel):
    """Everything the live interviewer is allowed to know. No doc fields
    exist on this model on purpose."""

    question_text: str
    persona: PersonaParams
    round: RoundProfile
    live_transcript: str = ""
    recent_context: str = ""


class GraderContext(BaseModel):
    transcript: str
    probes: list[ProbeRecord] = Field(default_factory=list)
    grader_notes: list[str] = Field(default_factory=list)
    duration_s: float = 0.0
    docs: list[Doc] = Field(default_factory=list)
    question_text: str = ""


class CoachContext(BaseModel):
    docs: list[Doc] = Field(default_factory=list)


class SessionManager:
    def __init__(self, cfg: SessionConfig, persona: PersonaParams):
        self.cfg = cfg
        self.round = cfg.round_profile()
        self.persona = persona

    # ---- context assembly (the wall) ----

    def interviewer_context(self, question: Question,
                            state: AnswerState | None = None) -> InterviewerContext:
        transcript = state.transcript_partial if state else ""
        sentences = [s.strip() for s in transcript.replace("?", ".").split(".")
                     if s.strip()]
        return InterviewerContext(
            question_text=question.text,
            persona=self.persona,
            round=self.round,
            live_transcript=transcript,
            recent_context=". ".join(sentences[-2:]),
        )

    def grader_context(self, question: Question, transcript: str,
                       state: AnswerState, duration_s: float) -> GraderContext:
        return GraderContext(
            transcript=transcript,
            probes=state.probes_fired,
            grader_notes=state.grader_notes,
            duration_s=duration_s,
            docs=self.user_docs(),
            question_text=question.text,
        )

    def coach_context(self) -> CoachContext:
        return CoachContext(docs=self.user_docs())

    def user_docs(self) -> list[Doc]:
        """Docs supplied this session, any subset. The bio is persona input,
        not answer material, so it stays out of grading and coaching too."""
        return [Doc(name=k, text=v) for k, v in self.cfg.materials.items()
                if k in USER_DOC_KEYS and k != "bio" and v.strip()]

    # ---- prompt rendering ----

    def interviewer_system_prompt(self, ctx: InterviewerContext) -> str:
        band = ctx.round.length_band_s
        return load_prompt("interviewer_system", {
            "persona_display_name": ctx.persona.display_name,
            "profile_id": ctx.round.profile_id,
            "time_budget_s": str(ctx.round.time_budget_s),
            "depth_style": ctx.round.depth_style.value,
            "emotional_probing_state":
                "on" if ctx.round.emotional_probe_weight > 0 else "off",
            "length_band_low": str(band[0]),
            "length_band_high": str(band[1]),
            "topic_emphasis": ", ".join(ctx.persona.topic_emphasis) or "none",
            "intensity": str(ctx.persona.intensity),
            "intensity_descriptor":
                INTENSITY_DESCRIPTORS[ctx.persona.intensity],
            "opening_style": ctx.persona.opening_style,
            "recent_context": ctx.recent_context or "(answer not started)",
        })

    def new_answer_state(self, question: Question) -> AnswerState:
        return AnswerState(
            question=question,
            round=self.round,
            persona=self.persona,
            interrupt_budget=self.persona.interrupt_budget,
        )
