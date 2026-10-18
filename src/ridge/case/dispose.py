"""Case disposal by crypto-erasure (PRD FR-26, PRIV-2).

Disposal is refused under legal hold and before the retention date (unless explicitly
overridden), and needs the case id typed back as confirmation. Order of operations, so a
crash can never leave a "disposed" record for a case that is still decryptable:

1. ``case.json`` is replaced by an ``erasing`` stub that no longer holds the wrapped data
   key (crypto-erasure; from here on the case is unreadable) and carries the pending record;
2. the disposal record is published next to the store;
3. the case folder is deleted.

Running ``dispose`` again on an ``erasing`` stub finishes steps 2-3. The retained record
holds no personal data: the examiner's registered key id instead of a name, and a reason
code from a fixed list instead of free text.

Limits: deleted files may persist on SSDs or in backups. That is why the key is destroyed
first: without it the remnants cannot be decrypted. Backups of ``case.json`` taken before
disposal would still hold the wrapped key; lab backup policy must account for this.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ridge.case.case_model import CASE_FILE, ERASING_SCHEMA
from ridge.case.custody import utc_now
from ridge.case.keys import KeyStore
from ridge.case.store import open_case
from ridge.errors import IntegrityError, RetentionError
from ridge.image_io import publish

RECORD_SCHEMA = "ridge.disposal/1"
REASONS = ("retention-expired", "proceedings-closed", "court-order", "legal-obligation", "created-in-error")


def dispose_case(
    case_dir: Path,
    passphrase: str,
    keystore: KeyStore,
    *,
    confirm_case_id: str,
    reason: str,
    actor_key_id: str,
    before_retention: bool = False,
) -> Path:
    """Crypto-erase a case and return the path of the retained disposal record."""
    raw = _read_json(case_dir / CASE_FILE)
    if confirm_case_id != raw.get("case_id") or confirm_case_id != case_dir.name:
        raise RetentionError("the confirmation does not match the case id; nothing was deleted")
    if raw.get("schema") == ERASING_SCHEMA:  # an earlier disposal was interrupted after erasure
        return _finish(case_dir, raw["record"])
    if reason not in REASONS:
        raise RetentionError(f"reason must be one of: {', '.join(REASONS)}")
    with open_case(case_dir, passphrase, keystore) as case:
        meta = case.meta()
        if meta.legal_hold:
            raise RetentionError("the case is under legal hold; lift the hold first")
        if datetime.now(UTC).date() < meta.retention_until and not before_retention:
            raise RetentionError(
                f"the retention period runs until {meta.retention_until.isoformat()}; "
                "use --before-retention to dispose earlier (this is recorded)"
            )
        case.custody.append("case.dispose", reason=reason, before_retention=before_retention)
        head, entries = case.custody.head, case.custody.next_seq

    record = {
        "schema": RECORD_SCHEMA,
        "case_id": confirm_case_id,
        "disposed_utc": utc_now(),
        "examiner_key_id": actor_key_id,
        "reason": reason,
        "before_retention": before_retention,
        "custody_head": head,
        "custody_entries": entries,
    }
    stub = {"schema": ERASING_SCHEMA, "case_id": confirm_case_id, "record": record}
    publish(case_dir / CASE_FILE, json.dumps(stub).encode("utf-8"), overwrite=True)  # 1. the key is gone
    return _finish(case_dir, record)


def _finish(case_dir: Path, record: dict[str, Any]) -> Path:
    record_path = case_dir.parent / f"{record['case_id']}.disposal.json"
    if not record_path.exists():
        publish(record_path, json.dumps(record, indent=2).encode("utf-8"))  # 2. the record
    shutil.rmtree(case_dir)  # 3. the remnants
    return record_path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IntegrityError(f"cannot read {path.name}: {exc}") from None
    if not isinstance(value, dict):
        raise IntegrityError(f"{path.name} is not a JSON object")
    return value
