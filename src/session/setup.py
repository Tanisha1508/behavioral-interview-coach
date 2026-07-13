"""Setup wizard (spec 2.1): profile, session type, materials, question
source -> SessionConfig. run_wizard() is the interactive path; SessionConfig
can also be built directly for tests and evals.
"""

from __future__ import annotations

import enum
from pathlib import Path

from pydantic import BaseModel, Field
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from src.engine.state import BUNDLED_PROFILE_IDS, RoundProfile, load_round_profile

ROOT = Path(__file__).resolve().parents[2]


class SessionType(str, enum.Enum):
    DRILL = "DRILL"
    SIMULATION = "SIMULATION"


class QuestionSourceConfig(BaseModel):
    scripted: list[str] = Field(default_factory=list)
    use_pack: bool = False
    bank_count: int = 3
    intel_text: str = ""


class SessionConfig(BaseModel):
    profile_id: str
    # interview: Drill/Simulation with the interviewer agent.
    # coach: voice coaching session grounded in the user's documents.
    mode: str = "interview"
    session_type: SessionType = SessionType.DRILL
    # listen: hear the full answer, then feedback (MVP default).
    # probing: up to engine.max_followups follow-ups after the answer.
    followup_mode: str = "listen"
    duration_min: int | None = None  # SIMULATION only
    materials: dict[str, str] = Field(default_factory=dict)  # resume|jd|bio|stories
    source: QuestionSourceConfig = Field(default_factory=QuestionSourceConfig)
    persona_overrides: dict = Field(default_factory=dict)

    def round_profile(self) -> RoundProfile:
        return load_round_profile(ROOT / "config" / "rounds" / f"{self.profile_id}.yaml")


def _paste_multiline(console: Console, label: str) -> str:
    console.print(f"[bold]{label}[/bold] (paste, then a line with only END):")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def run_wizard() -> SessionConfig:
    console = Console()
    console.print("[bold cyan]Behavioral Interview Coach: setup[/bold cyan]")

    profile = Prompt.ask("Round profile",
                         choices=sorted(BUNDLED_PROFILE_IDS), default="pm")
    session_type = SessionType(Prompt.ask(
        "Session type", choices=["DRILL", "SIMULATION"], default="DRILL"))
    console.print("[dim]listen: full answer, then feedback. "
                  "probing: follow-up questions after your answer.[/dim]")
    followup_mode = Prompt.ask("Interview mode",
                               choices=["listen", "probing"],
                               default="listen")
    duration = None
    if session_type == SessionType.SIMULATION:
        duration = IntPrompt.ask("Duration minutes (15-60)", default=20)

    materials: dict[str, str] = {}
    for doc in ("resume", "jd", "bio", "stories"):
        if Confirm.ask(f"Paste {doc}?", default=False):
            text = _paste_multiline(console, doc)
            if text.strip():
                materials[doc] = text

    source = QuestionSourceConfig()
    src_choice = Prompt.ask("Question source",
                            choices=["scripted", "pack", "bank", "intel", "blend"],
                            default="bank")
    if src_choice in ("scripted", "blend"):
        raw = _paste_multiline(console, "Scripted questions, one per line")
        source.scripted = [q.strip() for q in raw.splitlines() if q.strip()]
    if src_choice in ("pack", "blend"):
        if "resume" not in materials:
            console.print("[red]Pack source needs a resume. Paste it now.[/red]")
            materials["resume"] = _paste_multiline(console, "resume")
        source.use_pack = True
    if src_choice in ("bank", "blend"):
        source.bank_count = IntPrompt.ask("How many bank questions", default=3)
    else:
        source.bank_count = 0
    if src_choice in ("intel", "blend"):
        source.intel_text = _paste_multiline(console, "Pasted intel")

    return SessionConfig(profile_id=profile, session_type=session_type,
                         followup_mode=followup_mode, duration_min=duration,
                         materials=materials, source=source)


def main() -> None:
    """Run the wizard and stage the config for the agent to pick up."""
    from src.session import store

    cfg = run_wizard()
    for name, text in cfg.materials.items():
        store.save_doc(name, text)
    out = ROOT / "data" / "next_session.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(cfg.model_dump_json(indent=2))
    Console().print(f"[green]Ready. Config staged at {out}. "
                    "Interviewer will begin when you run: "
                    "python -m src.agent console[/green]")


if __name__ == "__main__":
    main()
