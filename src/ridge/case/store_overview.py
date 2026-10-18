"""Case overview of a store: references, retention and hold of every case, with one passphrase.

Case references, legal bases and retention dates are encrypted per case (architecture §8.1), so
the plaintext listing shows case ids only. With the examiner passphrase each active case is
opened just long enough to read its metadata and count its items, then closed. Nothing is
written: reading case metadata is not a read of evidence and adds no custody entry. Cases that
cannot be opened are named with the reason.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ridge.case.identity import unlock_identity
from ridge.case.keys import KeyStore
from ridge.case.listing import list_cases
from ridge.case.store import open_case
from ridge.errors import RidgeError


@dataclass(frozen=True)
class CaseOverview:
    """One case as the overview shows it."""

    case_id: str
    state: str
    reference: str | None = None
    retention_until: str | None = None
    legal_hold: bool | None = None
    due: bool | None = None  # retention date reached and no legal hold: disposal may be considered
    evidence: int | None = None
    jobs: int | None = None
    problem: str | None = None

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


def store_overview(store: Path, passphrase: str, keystore: KeyStore, *, today: str | None = None) -> list[CaseOverview]:
    """Read the metadata of every active case; a wrong passphrase stops before any case is opened."""
    unlock_identity(store, passphrase, keystore)
    day = today or datetime.now(UTC).date().isoformat()
    overview: list[CaseOverview] = []
    for summary in list_cases(store):
        if summary.state != "active":
            overview.append(CaseOverview(summary.case_id, summary.state))
            continue
        try:
            with open_case(store / summary.case_id, passphrase, keystore) as case:
                meta = case.meta()
                items = case.items()
                jobs = sum(1 for e in case.entries if e["action"] == "job.start")
        except RidgeError as exc:
            overview.append(CaseOverview(summary.case_id, summary.state, problem=str(exc)))
            continue
        retention = meta.retention_until.isoformat()
        overview.append(
            CaseOverview(
                summary.case_id,
                summary.state,
                reference=meta.case_reference,
                retention_until=retention,
                legal_hold=meta.legal_hold,
                due=retention <= day and not meta.legal_hold,
                evidence=sum(1 for i in items if i.role == "evidence"),
                jobs=jobs,
            )
        )
    return overview
