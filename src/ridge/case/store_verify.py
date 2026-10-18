"""Verify every case of a store in one run (PRD FR-24, ISO/IEC 27037 integrity monitoring).

One examiner passphrase unlocks the identity and all of that examiner's cases, so a periodic
integrity check of a whole store needs it once. Each active case is opened, verified exactly as
``ridge-case verify`` does (the verification is logged in that case's custody log) and closed
again. Cases that cannot be checked are reported, never skipped silently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ridge.case.identity import unlock_identity
from ridge.case.keys import KeyStore
from ridge.case.listing import list_cases
from ridge.case.store import open_case
from ridge.case.verify import verify_case
from ridge.errors import RidgeError

NOT_CHECKED = {
    "locked": "open in another Ridge window; not checked",
    "disposed": "disposed; only the disposal record remains",
}
FAULTS = {
    "erasing": "disposal was interrupted; finish it with ridge-case dispose",
    "invalid": "the case folder is unreadable or not a Ridge case",
}


@dataclass
class CaseCheck:
    """The outcome for one case of the store."""

    case_id: str
    state: str
    checked: bool
    ok: bool
    reference: str | None = None
    items: int = 0
    reports: int = 0
    problems: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


def verify_store(store: Path, passphrase: str, keystore: KeyStore) -> list[CaseCheck]:
    """Verify every active case of `store`; a wrong passphrase stops before any case is opened."""
    unlock_identity(store, passphrase, keystore)  # refuses a wrong passphrase once, up front
    results: list[CaseCheck] = []
    for summary in list_cases(store):
        if summary.state != "active":
            fault = FAULTS.get(summary.state)
            note = fault or NOT_CHECKED.get(summary.state, summary.state)
            results.append(CaseCheck(summary.case_id, summary.state, False, fault is None, problems=[note]))
            continue
        results.append(_check(store, summary.case_id, passphrase, keystore))
    return results


def _check(store: Path, case_id: str, passphrase: str, keystore: KeyStore) -> CaseCheck:
    try:
        with open_case(store / case_id, passphrase, keystore) as case:
            reference = case.meta().case_reference
            result = verify_case(case, store)
    except RidgeError as exc:  # e.g. a broken custody chain refuses to open, or another examiner's case
        return CaseCheck(case_id, "active", True, False, problems=[str(exc)])
    return CaseCheck(case_id, "active", True, result.ok, reference, result.items, result.reports, list(result.problems))
