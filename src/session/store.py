"""User library (spec 5.2): resume, docs, packs, session history -> ./data/."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"
SESSIONS_DIR = DATA_DIR / "sessions"


def save_doc(name: str, text: str) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCS_DIR / f"{name}.txt"
    path.write_text(text)
    return path


def load_doc(name: str) -> str | None:
    path = DOCS_DIR / f"{name}.txt"
    return path.read_text() if path.exists() else None


def list_docs() -> list[str]:
    if not DOCS_DIR.exists():
        return []
    return sorted(p.stem for p in DOCS_DIR.glob("*.txt"))


def save_session(record: dict) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SESSIONS_DIR / f"session_{stamp}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    return path


def load_sessions() -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    return [json.loads(p.read_text())
            for p in sorted(SESSIONS_DIR.glob("session_*.json"))]
