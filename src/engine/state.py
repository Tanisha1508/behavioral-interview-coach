"""Engine state: RoundProfile, Question, AnswerState (spec Sections 3, 3.1).

RoundProfile carries every format-specific parameter. Engine code reads
these values and never branches on profile_id.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

BUNDLED_PROFILE_IDS = {"pm", "consulting", "mba_admissions", "tech", "others"}


class DepthStyle(str, enum.Enum):
    BREADTH = "BREADTH"
    ONE_STORY_DEEP = "ONE_STORY_DEEP"


class RoundProfile(BaseModel):
    profile_id: str
    time_budget_s: int = Field(gt=0)
    we_ratio_threshold: float = Field(ge=0.0, le=1.0)
    emotional_probe_weight: float = Field(ge=0.0, le=1.0)
    patience_ms: int = Field(gt=0)
    length_band_s: tuple[int, int]
    depth_style: DepthStyle
    probe_bias: dict[str, float] = Field(default_factory=dict)

    @field_validator("length_band_s")
    @classmethod
    def band_ordered(cls, v: tuple[int, int]) -> tuple[int, int]:
        if v[0] >= v[1]:
            raise ValueError(f"length_band_s must be [low, high], got {v}")
        return v


class Question(BaseModel):
    id: str
    text: str
    expected_buckets: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    source: str = "bank"  # scripted | pack | bank | intel


def load_round_profile(path: str | Path) -> RoundProfile:
    with open(path) as f:
        return RoundProfile(**yaml.safe_load(f))


def load_bank(path: str | Path) -> list[Question]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return [Question(**q) for q in raw["questions"]]


class SectionStatus(str, enum.Enum):
    NOT_SEEN = "NOT_SEEN"
    SEEN = "SEEN"


HSCARR_SECTIONS = ["hook", "situation", "complication", "action", "resolution", "reflection"]


class SignalSet(BaseModel):
    """Analyzer output (spec 3.2). All rule-based, no LLM."""

    vague_claim: bool = False
    vague_phrase: Optional[str] = None
    we_flag: bool = False
    we_ratio: float = 0.0
    missing_numbers: bool = False
    skipped_section: bool = False
    skipped_detail: Optional[str] = None
    rambling: bool = False
    overrun: bool = False
    stalled: bool = False
    deflected: bool = False


class ProbeType(str, enum.Enum):
    SPECIFICITY = "SPECIFICITY"
    OWNERSHIP = "OWNERSHIP"
    QUANTIFY = "QUANTIFY"
    DEPTH = "DEPTH"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    REDIRECT = "REDIRECT"
    REDIRECT_WRAP = "REDIRECT_WRAP"
    EMOTIONAL = "EMOTIONAL"
    NUDGE = "NUDGE"


class ProbeCandidate(BaseModel):
    probe_type: ProbeType
    priority: int  # 1 is highest (spec 3.3 ordering)
    confidence: float
    detail: str = ""  # offending phrase or signal detail for probe text


class ProbeRecord(BaseModel):
    probe_type: ProbeType
    fired_at_ms: int
    trigger: str  # which signal caused it
    text: str = ""
    interrupted: bool = False  # True if it cut in, False if asked at a pause


class Floor(str, enum.Enum):
    USER = "USER"
    INTERVIEWER = "INTERVIEWER"
    SILENCE = "SILENCE"


class PersonaParams(BaseModel):
    """Resolved persona (spec 4.3). Style within round-format rules."""

    persona_id: str
    display_name: str
    round_profile: str
    probe_mix: dict[str, float]
    intensity: int = Field(ge=1, le=5)
    interrupt_eagerness: float
    interrupt_budget: int
    patience_ms: int
    time_budget_s: int
    topic_emphasis: list[str] = Field(default_factory=list)
    opening_style: str = "neutral"
    voice_preset: str = "neutral_default"
    speaking_rate: float = 1.0


class AnswerState(BaseModel):
    """Live state for one answer (spec 3.1)."""

    question: Question
    round: RoundProfile
    persona: PersonaParams
    clock_ms: int = 0
    transcript_partial: str = ""
    hscarr_progress: dict[str, SectionStatus] = Field(
        default_factory=lambda: {s: SectionStatus.NOT_SEEN for s in HSCARR_SECTIONS}
    )
    signals: SignalSet = Field(default_factory=SignalSet)
    probes_fired: list[ProbeRecord] = Field(default_factory=list)
    interrupt_budget: int = 2
    floor: Floor = Floor.USER
    last_interrupt_ms: int = -10**9  # far past so the first probe is never cooldown-gated
    silence_started_ms: Optional[int] = None
    deflect_count: int = 0
    pre_probe_transcript: str = ""  # snapshot at last probe, for deflection check
    user_signaled_done: bool = False
    queued_probes: list[ProbeCandidate] = Field(default_factory=list)
    grader_notes: list[str] = Field(default_factory=list)
