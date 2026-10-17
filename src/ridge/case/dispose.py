"""Case disposal by crypto-erasure (PRD FR-26, PRIV-2).

Disposal is refused under legal hold and before the retention date (unless explicitly
overridden with a reason), and needs the case id typed back as confirmation. The wrapped
data key is destroyed first, then the files are deleted. A small plaintext record without
personal data is kept next to the store for the processing log.

Limits: deleted files may persist on SSDs or in backups. That is why the key is destroyed
first: without it the remnants cannot be decrypted. Backups of ``case.json`` taken before
disposal would still hold the wrapped key; lab backup policy must account for this.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ridge.case.custody import default_actor, utc_now
from ridge.case.keys import KeyStore
from ridge.case.store import CASE_FILE, clean_text, open_case, read_case_record
from ridge.errors import RetentionError
from ridge.image_io import publish

RECORD_SCHEMA = "ridge.disposal/1"


def dispose_case(
    case_dir: Path,
    passphrase: str,
    keystore: KeyStore,
    *,
    confirm_case_id: str,
    reason: str,
    before_retention: bool = False,
    actor: str | None = None,
) -> Path:
    """Crypto-erase a case and return the path of the retained disposal record."""
    case_id = read_case_record(case_dir)["case_id"]
    if confirm_case_id != case_id:
        raise RetentionError("the confirmation does not match the case id; nothing was deleted")
    reason = clean_text(reason, "reason", 500)
    actor = actor or default_actor()
    with open_case(case_dir, passphrase, keystore, actor) as case:
        meta = case.meta()
        if meta.legal_hold:
            raise RetentionError("the case is under legal hold; lift the hold first")
        if datetime.now(UTC).date() < meta.retention_until and not before_retention:
            raise RetentionError(
                f"the retention period runs until {meta.retention_until.isoformat()}; "
                "use --before-retention to dispose earlier (the reason is recorded)"
            )
        case.custody.append("case.dispose", reason=reason, before_retention=before_retention)
        head, entries = case.custody.head, case.custody.next_seq

    record = {
        "schema": RECORD_SCHEMA,
        "case_id": case_id,
        "disposed_utc": utc_now(),
        "actor": actor,
        "reason": reason,
        "before_retention": before_retention,
        "custody_head": head,
        "custody_entries": entries,
    }
    record_path = case_dir.parent / f"{case_id}.disposal.json"
    publish(record_path, json.dumps(record, indent=2).encode("utf-8"))
    # Crypto-erase: replace case.json with a stub that no longer holds the wrapped key, then delete.
    stub = {"schema": "ridge.case/1", "case_id": case_id, "disposed_utc": record["disposed_utc"]}
    publish(case_dir / CASE_FILE, json.dumps(stub).encode("utf-8"), overwrite=True)
    shutil.rmtree(case_dir)
    return record_path
