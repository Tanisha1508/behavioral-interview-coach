"""Bio -> tags (spec 4.2). One LLM call, strict JSON, and the
verbatim-or-UNKNOWN rule is enforced here in code: any tag whose cited
phrase is not an exact substring of the bio is reset to UNKNOWN.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.llm.client import complete

FIRM_TYPES = {"MBB", "BIG_TECH", "STARTUP", "FINANCE", "OTHER", "UNKNOWN"}
FUNCTIONS = {"CONSULTING_PARTNER", "CONSUMER_PM", "TECHNICAL_PM",
             "PLATFORM_PM", "ENG_LEADER", "RECRUITER", "UNKNOWN"}
SENIORITIES = {"PARTNER_DIRECTOR", "SENIOR", "MID", "UNKNOWN"}


class Signal(BaseModel):
    tag: str
    phrase: str


class PersonaTags(BaseModel):
    firm_type: str = "UNKNOWN"
    function: str = "UNKNOWN"
    seniority: str = "UNKNOWN"
    domain_tags: list[str] = Field(default_factory=list)
    signals_found: list[Signal] = Field(default_factory=list)


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _cited(field: str, value: str, signals: list[Signal], bio_norm: str) -> bool:
    """True if some signal cites this field with a phrase verbatim in the bio."""
    for s in signals:
        if s.tag.split("=")[0].strip() == field or field in s.tag:
            if _normalize(s.phrase) and _normalize(s.phrase) in bio_norm:
                return True
    return False


def extract_tags(bio_text: str) -> PersonaTags:
    if not bio_text.strip():
        return PersonaTags()

    result = complete("persona_extract", {"bio_text": bio_text},
                      json_schema={"type": "object"})
    raw = result.parsed or {}

    signals = []
    for s in raw.get("signals_found", []):
        try:
            signals.append(Signal(tag=str(s.get("tag", "")),
                                  phrase=str(s.get("phrase", ""))))
        except Exception:
            continue

    bio_norm = _normalize(bio_text)
    # Keep only signals whose phrase is verbatim in the bio.
    signals = [s for s in signals if _normalize(s.phrase) in bio_norm]

    tags = PersonaTags(signals_found=signals)

    firm = str(raw.get("firm_type", "UNKNOWN")).upper()
    if firm in FIRM_TYPES and firm != "UNKNOWN" and _cited("firm_type", firm, signals, bio_norm):
        tags.firm_type = firm

    func = str(raw.get("function", "UNKNOWN")).upper()
    if func in FUNCTIONS and func != "UNKNOWN" and _cited("function", func, signals, bio_norm):
        tags.function = func

    sen = str(raw.get("seniority", "UNKNOWN")).upper()
    if sen in SENIORITIES and sen != "UNKNOWN" and _cited("seniority", sen, signals, bio_norm):
        tags.seniority = sen

    # domain_tags shift topic emphasis only, never intensity (spec 4.2), so
    # they pass through without a citation requirement beyond sanity limits.
    tags.domain_tags = [str(t).lower() for t in raw.get("domain_tags", [])][:8]
    return tags
