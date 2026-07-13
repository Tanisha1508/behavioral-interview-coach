"""QuestionQueue compiler (spec 2.3): scripted, pack, bank, pasted intel,
blended in that order. Bank sampling is weighted by persona topic emphasis.
"""

from __future__ import annotations

import random
from pathlib import Path

from src.engine.state import Question, load_bank
from src.session.setup import SessionConfig

ROOT = Path(__file__).resolve().parents[2]


def _bank_sample(profile_id: str, count: int, topic_emphasis: list[str],
                 rng: random.Random) -> list[Question]:
    if count <= 0:
        return []
    bank = load_bank(ROOT / "config" / "banks" / f"{profile_id}.yaml")
    emphasized = set(topic_emphasis)

    def weight(q: Question) -> float:
        overlap = len(emphasized & set(q.topics))
        return 1.0 + 2.0 * overlap

    picked: list[Question] = []
    pool = list(bank)
    while pool and len(picked) < count:
        weights = [weight(q) for q in pool]
        choice = rng.choices(pool, weights=weights, k=1)[0]
        picked.append(choice)
        pool.remove(choice)
    return picked


def compile_queue(cfg: SessionConfig, topic_emphasis: list[str] | None = None,
                  pack_questions: list[Question] | None = None,
                  intel_questions: list[Question] | None = None,
                  seed: int | None = None) -> list[Question]:
    """Pack and intel questions are compiled by their owners (coach/ modules,
    which may see user docs) and passed in here; the queue itself never
    touches doc content."""
    rng = random.Random(seed)
    queue: list[Question] = []

    for i, text in enumerate(cfg.source.scripted):
        queue.append(Question(id=f"scripted_{i + 1:02d}", text=text,
                              source="scripted"))
    if cfg.source.use_pack and pack_questions:
        queue.extend(pack_questions)
    queue.extend(_bank_sample(cfg.profile_id, cfg.source.bank_count,
                              topic_emphasis or [], rng))
    if intel_questions:
        queue.extend(intel_questions)

    # De-duplicate on text, order preserved.
    seen: set[str] = set()
    unique = []
    for q in queue:
        key = q.text.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique
