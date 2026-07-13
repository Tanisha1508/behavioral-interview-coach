"""Coach mode console entry: pack + coverage map + rewrite notes.

Usage:
  python -m src.coach.cli --resume path --jd path [--stories path]
      [--answer path --question "text"] [--profile pm]

Reads docs from files (or data/docs/ names saved by the wizard), prints the
pack, the coverage map when stories are supplied, and rewrite notes when an
answer is supplied.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.coach import coverage as coverage_mod
from src.coach import questions as questions_mod
from src.coach import rewrites as rewrites_mod
from src.engine.state import load_round_profile
from src.grading.ammo import Doc
from src.session import store

ROOT = Path(__file__).resolve().parents[2]


def _read(source: str | None) -> str:
    if not source:
        return ""
    path = Path(source)
    if path.exists():
        return path.read_text()
    return store.load_doc(source) or ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Coach mode")
    parser.add_argument("--resume", required=True)
    parser.add_argument("--jd", required=True)
    parser.add_argument("--stories")
    parser.add_argument("--answer")
    parser.add_argument("--question")
    parser.add_argument("--profile", default="pm")
    args = parser.parse_args()

    console = Console()
    round_profile = load_round_profile(
        ROOT / "config" / "rounds" / f"{args.profile}.yaml")
    resume, jd = _read(args.resume), _read(args.jd)
    if not resume.strip() or not jd.strip():
        console.print("[red]Resume and JD are required for a pack.[/red]")
        return

    console.print("[bold cyan]Generating question pack...[/bold cyan]")
    pack = questions_mod.generate_pack(resume, jd, round_profile)
    table = Table(title=f"Tailored pack ({args.profile})", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("Question")
    table.add_column("Bucket")
    table.add_column("Targets (resume line)")
    table.add_column("Why likely")
    for i, q in enumerate(pack.questions, 1):
        table.add_row(str(i), q.text, q.bucket, q.resume_line, q.why_likely)
    console.print(table)
    if pack.dropped:
        console.print(f"[yellow]{pack.dropped} question(s) dropped: "
                      "resume_line not verbatim in resume.[/yellow]")

    stories = _read(args.stories)
    if stories.strip():
        console.print("\n[bold cyan]Mapping story coverage...[/bold cyan]")
        report = coverage_mod.coverage_map(stories, pack)
        ctable = Table(title="Coverage map", show_lines=True)
        ctable.add_column("Question")
        ctable.add_column("Covered by")
        ctable.add_column("Strength")
        ctable.add_column("Note")
        for e in report.entries:
            style = {"STRONG": "green", "PARTIAL": "yellow",
                     "GAP": "red"}[e.strength]
            ctable.add_row(e.question, e.covered_by or "-",
                           f"[{style}]{e.strength}[/{style}]", e.note)
        console.print(ctable)
        console.print(f"[bold]{len(report.gaps)} gap(s) flagged.[/bold]")

    answer = _read(args.answer)
    if answer.strip():
        question = args.question or (pack.questions[0].text
                                     if pack.questions else "")
        console.print("\n[bold cyan]Rewrite notes...[/bold cyan]")
        docs = [Doc(name="resume", text=resume)]
        if stories.strip():
            docs.append(Doc(name="stories", text=stories))
        rw = rewrites_mod.rewrite(question, answer, round_profile, docs)
        for note in rw.notes:
            console.print(f"[bold]{note.dimension}[/bold]: {note.problem}")
            console.print(f"  fix: {note.fix}")
        console.print("\n[bold]Rewritten answer:[/bold]")
        console.print(rw.rewritten_answer)


if __name__ == "__main__":
    main()
