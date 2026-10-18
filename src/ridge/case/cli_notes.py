"""``ridge-case`` examiner notes: add a note to a case, a job or a stored item; list the notes.

ridge-case note CASE "TEXT" [--job JOB] [--item SHA] [--corrects SEQ]
ridge-case notes CASE [--job JOB]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.notes import Note, add_note, list_notes
from ridge.case.reports import printable
from ridge.case.store import open_case


def _line(note: Note) -> str:
    about = f"job {note.job_id}" if note.job_id else "case"
    about += f", item {note.sha256[:12]}" if note.sha256 else ""
    fix = f", corrects #{note.corrects}" if note.corrects is not None else ""
    lines = [f"#{note.seq}  {note.ts_utc}  {printable(note.actor)}  ({about}{fix})"]
    lines += [f"    {printable(line)}" for line in note.text.splitlines()]
    return "\n".join(lines)


def cmd_note(args: argparse.Namespace) -> None:
    """Append an examiner note (logged; notes are never changed or removed)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        note = add_note(case, args.text, job_id=args.job, sha256=args.item, corrects=args.corrects)
    common.say(f"note #{note.seq} added")


def cmd_notes(args: argparse.Namespace) -> None:
    """List the examiner notes of a case or one job."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        notes = list_notes(case.entries, job_id=args.job)
    common.say("\n".join(_line(n) for n in notes) if notes else "no notes")


def add_commands(sub: Any) -> None:
    """Register the note commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("note", help="add an examiner note to the case, a job or a stored item (logged)")
    p.add_argument("case", type=Path)
    p.add_argument("text")
    p.add_argument("--job")
    p.add_argument("--item", metavar="SHA")
    p.add_argument("--corrects", type=int, metavar="SEQ", help="the note this one corrects (it stays in the log)")
    p.set_defaults(func=cmd_note)
    p = sub.add_parser("notes", help="list the examiner notes")
    p.add_argument("case", type=Path)
    p.add_argument("--job")
    p.set_defaults(func=cmd_notes)
