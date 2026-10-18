"""A one-screen summary of an open case, read from its metadata and verified custody log.

Counts and dates only: what is stored, how many jobs ran and how they ended, notes, and when the
case was last verified or its custody head last exported. Reading the summary decrypts no
evidence and adds no custody entry.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from ridge.case.notes import list_notes
from ridge.case.reports import list_jobs
from ridge.case.store import OpenCase


@dataclass(frozen=True)
class CaseStatus:
    """What the summary shows."""

    case_id: str
    reference: str
    retention_until: str
    legal_hold: bool
    retention_reached: bool
    items: dict[str, int]
    jobs: dict[str, int]
    signed_reports: int
    notes: int
    entries: int
    last_verified: str | None
    last_verify_result: str | None
    last_head_export: str | None

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


def _last(case: OpenCase, action: str) -> dict[str, Any] | None:
    return next((e for e in reversed(case.entries) if e["action"] == action), None)


def case_status(case: OpenCase, *, today: str | None = None) -> CaseStatus:
    """Summarise `case` (no evidence is read, nothing is logged)."""
    meta = case.meta()
    jobs = list_jobs(case.entries)
    verified = _last(case, "case.verify")
    head = _last(case, "head.export")
    retention = meta.retention_until.isoformat()
    day = today or datetime.now(UTC).date().isoformat()
    return CaseStatus(
        case_id=case.case_id,
        reference=meta.case_reference,
        retention_until=retention,
        legal_hold=meta.legal_hold,
        retention_reached=retention <= day,
        items=dict(Counter(item.role for item in case.items())),
        jobs=dict(Counter(job.result for job in jobs)),
        signed_reports=sum(1 for job in jobs if job.report_sha256),
        notes=len(list_notes(case.entries)),
        entries=len(case.entries),
        last_verified=verified["ts_utc"] if verified else None,
        last_verify_result=verified["result"] if verified else None,
        last_head_export=head["ts_utc"] if head else None,
    )


def render_status(status: CaseStatus) -> list[str]:
    """Text lines for the CLI."""
    hold = "legal hold" if status.legal_hold else ("retention date reached" if status.retention_reached else "")
    items = ", ".join(f"{n} {role}" for role, n in sorted(status.items.items())) or "nothing stored"
    jobs = ", ".join(f"{n} {result}" for result, n in sorted(status.jobs.items())) or "no jobs"
    verified = f"{status.last_verified} ({status.last_verify_result})" if status.last_verified else "never verified"
    return [
        f"Case {status.reference} ({status.case_id})",
        f"Keep until  {status.retention_until}  {hold}".rstrip(),
        f"Stored      {items}",
        f"Jobs        {jobs}; {status.signed_reports} signed report(s)",
        f"Notes       {status.notes}",
        f"Verified    {verified}",
        f"Head export {status.last_head_export or 'none'}",
        f"Custody log {status.entries} entries",
    ]
