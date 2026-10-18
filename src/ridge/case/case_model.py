"""The case store's records and rules that do not need an open case (architecture §8.1).

File names and schemas, stored roles, the case metadata and stored-item records, free-text
validation, and the publish-then-log rule for plaintext leaving the store (FR-22, FR-25).
`ridge.case.store` re-exports these names, so callers keep importing them from there.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ridge.errors import ParameterError
from ridge.image_io import publish

CASE_FILE, META_FILE, LOCK_FILE = "case.json", "meta.enc", "LOCK"
SCHEMA = "ridge.case/1"
ERASING_SCHEMA = "ridge.case-erasing/1"  # case.json after crypto-erasure, before deletion
ROLES = {
    "evidence": "evidence",
    "reference": "references",  # NAFIS/AFIS candidate images for side-by-side viewing (FR-52), never processed
    "print": "artefacts",
    "debug": "artefacts",
    "export": "artefacts",
    "minutiae": "artefacts",
}
IMPORT_ACTIONS = {"evidence": "evidence.import", "reference": "reference.import"}  # stored from outside a job
ITEM_ACTIONS = (*IMPORT_ACTIONS.values(), "artefact.write")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class CaseMeta:
    """Case metadata kept encrypted in meta.enc."""

    case_reference: str
    legal_basis: str
    retention_until: date
    legal_hold: bool = False

    def to_json(self) -> dict[str, Any]:
        """JSON form."""
        return {**asdict(self), "retention_until": self.retention_until.isoformat()}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CaseMeta:
        """Parse stored metadata."""
        return cls(
            data["case_reference"], data["legal_basis"], date.fromisoformat(data["retention_until"]), data["legal_hold"]
        )


@dataclass(frozen=True)
class StoredItem:
    """One stored blob as recorded in the custody log."""

    sha256: str
    role: str
    size: int
    label: str
    job_id: str | None = None
    source: str | None = None  # where a reference image came from (examiner's note)


def publish_logged(files: Sequence[tuple[Path, bytes]], log: Callable[[], object], *, overwrite: bool) -> None:
    """Write plaintext files, then log the export; if anything fails, remove what was written.

    Data leaves the store only together with its custody entry (FR-22, FR-25): a failed second
    file or a failed log append never leaves an unlogged plaintext copy behind. Files that existed
    before are never removed unless this call replaced them (`overwrite`).
    """
    written: list[Path] = []
    try:
        for path, data in files:
            publish(path, data, overwrite=overwrite)
            written.append(path)
        log()
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise


def path_label(label: str) -> str:
    """Shorten a file label for messages (labels are already cleaned when stored)."""
    return label if len(label) <= 60 else label[:57] + "..."


def clean_text(value: str, what: str, limit: int = 200) -> str:
    """Validate free text: trimmed, 1..limit characters, no control characters."""
    value = value.strip()
    if not value or len(value) > limit or _CONTROL.search(value):
        raise ParameterError(f"{what} must be 1-{limit} printable characters")
    return value
