"""Examiner notes: contemporaneous observations kept in the case's custody log.

Notes are technical records (ISO/IEC 17025 §7.5, ISO 21043-2): who wrote what, when, about which
job or stored item. Like every custody entry they are encrypted, hash-chained and append-only; a
correction is a new note naming the note it corrects, so the original stays readable. Ridge keeps
the text exactly as the examiner wrote it and never interprets it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from ridge.case.custody import Entry
from ridge.case.store import OpenCase
from ridge.errors import ParameterError

ACTION = "examiner.note"
MAX_CHARS = 2000
# Control characters other than tab and line feed, and the bidirectional overrides and isolates
# that can make a record read differently from what is stored ("Trojan Source").
_REFUSED = re.compile("[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


@dataclass(frozen=True)
class Note:
    """One note as it stands in the custody log."""

    seq: int
    ts_utc: str
    actor: str
    text: str
    job_id: str | None = None
    sha256: str | None = None
    corrects: int | None = None  # sequence number of the note this one corrects

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


def clean_note(text: str) -> str:
    """Validate a note: 1..MAX_CHARS characters after trimming, line breaks allowed."""
    text = text.replace("\r\n", "\n").strip()
    if not text or len(text) > MAX_CHARS or _REFUSED.search(text):
        raise ParameterError(f"a note must be 1-{MAX_CHARS} printable characters (line breaks are allowed)")
    return text


def _note(entry: Entry) -> Note:
    return Note(
        entry["seq"],
        entry["ts_utc"],
        entry["actor"],
        entry["text"],
        entry.get("job_id"),
        entry.get("sha256"),
        entry.get("corrects"),
    )


def list_notes(entries: Iterable[Entry], *, job_id: str | None = None, sha256: str | None = None) -> list[Note]:
    """Every note of the case in log order, or only those about one job or one stored item."""
    notes = [_note(e) for e in entries if e["action"] == ACTION and e["result"] == "ok"]
    return [n for n in notes if (job_id is None or n.job_id == job_id) and (sha256 is None or n.sha256 == sha256)]


def add_note(
    case: OpenCase,
    text: str,
    *,
    job_id: str | None = None,
    sha256: str | None = None,
    corrects: int | None = None,
) -> Note:
    """Append a note about the case, one of its jobs or one stored item (logged as ``examiner.note``)."""
    text = clean_note(text)
    if corrects is not None:
        earlier = next((n for n in list_notes(case.entries) if n.seq == corrects), None)
        if earlier is None:
            raise ParameterError(f"custody entry {corrects} is not a note of this case")
        job_id = job_id or earlier.job_id  # a correction belongs where the corrected note does
        sha256 = sha256 or earlier.sha256
    if job_id is not None and not any(e["action"] == "job.start" and e.get("job_id") == job_id for e in case.entries):
        raise ParameterError(f"no job {job_id} in this case")
    if sha256 is not None:
        sha256 = case.item(sha256).sha256  # refuses an unknown or ambiguous item
    entry = case.custody.append(ACTION, text=text, job_id=job_id, sha256=sha256, corrects=corrects)
    case.entries.append(entry)
    return _note(entry)
