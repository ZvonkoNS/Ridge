"""Cases in a store, without a passphrase (PRD FR-50 open flow): ids, creation time and state only.

Everything listed here is already plaintext on disk: folder names, ``case.json`` and disposal
records. References, legal bases and contents stay encrypted until a case is unlocked. Folders
that are not Ridge cases are skipped, and a case.json that does not match its folder is listed
as ``invalid`` instead of hiding a tampered case.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ridge.case.dispose import RECORD_SCHEMA
from ridge.case.store import CASE_FILE, ERASING_SCHEMA, LOCK_FILE, SCHEMA
from ridge.errors import CaseError
from ridge.image_io import read_bounded

MAX_RECORD_BYTES = 64 * 1024
DISPOSAL_SUFFIX = ".disposal.json"


@dataclass(frozen=True)
class CaseSummary:
    """One case folder or disposal record of a store."""

    case_id: str
    state: str  # "active", "locked" (open elsewhere), "erasing" (disposal interrupted), "disposed", "invalid"
    created_utc: str | None = None
    disposed_utc: str | None = None

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


def _is_case_id(name: str) -> bool:
    try:
        return str(uuid.UUID(name)) == name
    except ValueError:
        return False


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(read_bounded(path, MAX_RECORD_BYTES).decode("utf-8"))
    except (OSError, ValueError):  # unreadable, oversized (InputRejectedError) or not JSON
        return None
    return value if isinstance(value, dict) else None


def _summary(folder: Path) -> CaseSummary:
    record = _read_json(folder / CASE_FILE)
    if record is None or record.get("case_id") != folder.name:
        return CaseSummary(folder.name, "invalid")
    if record.get("schema") == ERASING_SCHEMA:
        return CaseSummary(folder.name, "erasing")
    if record.get("schema") != SCHEMA:
        return CaseSummary(folder.name, "invalid")
    state = "locked" if (folder / LOCK_FILE).exists() else "active"
    created = record.get("created_utc")
    return CaseSummary(folder.name, state, created_utc=created if isinstance(created, str) else None)


def list_cases(store: Path) -> list[CaseSummary]:
    """Every case of `store` (newest first), plus completed disposals."""
    if not store.is_dir():
        raise CaseError(f"{store} is not a Ridge store folder")
    found: dict[str, CaseSummary] = {}
    for path in store.iterdir():
        if path.is_dir() and not path.is_symlink() and _is_case_id(path.name):
            found[path.name] = _summary(path)
    for path in store.glob(f"*{DISPOSAL_SUFFIX}"):
        case_id = path.name.removesuffix(DISPOSAL_SUFFIX)
        if not _is_case_id(case_id) or case_id in found:
            continue
        record = _read_json(path)
        disposed = None if record is None else record.get("disposed_utc")
        if record is None or record.get("schema") != RECORD_SCHEMA or record.get("case_id") != case_id:
            found[case_id] = CaseSummary(case_id, "invalid")  # a damaged record is shown, never trusted
        else:
            found[case_id] = CaseSummary(
                case_id, "disposed", disposed_utc=disposed if isinstance(disposed, str) else None
            )
    return sorted(found.values(), key=lambda c: (c.created_utc or c.disposed_utc or "", c.case_id), reverse=True)
