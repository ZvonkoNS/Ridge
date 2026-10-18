"""Processing record export (PRD PRIV-3): the custody log as a readable file that verifies offline.

The export holds every decrypted custody entry, the case id and the examiner's public key.
Before writing, Ridge logs ``log.export`` (naming the case id) and signs the custody head, so
every entry in the file, and the case id it claims, is covered by a signature.
`check_exported_log` recomputes the hash chain from the entries and checks every signed head
without the case store. It refuses a record that does not end with that signed export, so
appended entries or stripped signatures cannot pass. Like the log itself (R-5), the export cannot
show that entries were cut off after a signed head. The DPO compares the last entry with what
the examiner reports. The key id in the file must be compared with the examiner's published
identity, because the file carries its own public key.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ridge.case.crypto import sha256_hex
from ridge.case.custody import GENESIS, Entry, canonical, utc_now, verify_signed_heads
from ridge.case.identity import Signer, key_id_for, public_identity
from ridge.case.keys import b64
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, OutputExistsError
from ridge.image_io import publish, read_bounded

SCHEMA = "ridge.processing-record/1"
MAX_RECORD_BYTES = 64 * 1024 * 1024
NOTE = (
    "Processing record of a Ridge case (custody log). Verify with `ridge-case check-log`. "
    "Entries after the last chain.sign entry are not covered by a signature."
)


def export_log(case: OpenCase, store: Path, signer: Signer, dest: Path, *, overwrite: bool = False) -> int:
    """Log the export, sign the head, then write every entry to `dest`; returns the entry count."""
    if not overwrite and dest.exists():
        raise OutputExistsError(f"{dest.name} already exists (use --overwrite to replace)")
    key_id, public = public_identity(store)
    if signer.key_id != key_id:
        raise IntegrityError("the unlocked identity is not this store's examiner identity")
    case.entries.append(case.custody.append("log.export", destination=str(dest.resolve()), case_id=case.case_id))
    case.entries.append(case.custody.sign_head(signer))
    record = {
        "schema": SCHEMA,
        "case_id": case.case_id,
        "exported_utc": utc_now(),
        "identity": {"key_id": key_id, "public_key": b64(public)},
        "note": NOTE,
        "entries": case.entries,
    }
    data = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    try:
        publish(dest, data, overwrite=overwrite)
    except (OSError, OutputExistsError) as exc:
        case.entries.append(case.custody.append("log.export", result="failed", error=type(exc).__name__))
        raise
    return len(case.entries)


@dataclass(frozen=True)
class LogCheck:
    """Outcome of a successful `check_exported_log`."""

    case_id: str
    entries: int
    signed_heads: int
    key_id: str
    key_confirmed: bool


def check_exported_log(path: Path, *, expected_key_id: str | None = None) -> LogCheck:
    """Verify an exported processing record offline: chain links, sequence, signed heads, key."""
    return verify_record(load_record(path), expected_key_id=expected_key_id)[0]


def verify_record(record: dict[str, Any], *, expected_key_id: str | None = None) -> tuple[LogCheck, list[Entry]]:
    """Verify a parsed processing record; return the result and the entries that were verified.

    Callers that inspect entries (``check-head``) use these, never a second read of the file.
    """
    identity = record.get("identity")
    if not isinstance(identity, dict):
        raise IntegrityError("the record names no identity")
    try:
        public = base64.b64decode(str(identity.get("public_key")), validate=True)
    except (binascii.Error, ValueError):
        raise IntegrityError("the identity's public key is not base64") from None
    key_id = key_id_for(public)
    if identity.get("key_id") != key_id:
        raise IntegrityError("the identity's key id does not match its public key")
    if expected_key_id is not None and key_id != expected_key_id.strip().lower():
        raise IntegrityError(f"the record's key is {key_id}, not the expected key {expected_key_id}")
    entries = record.get("entries")
    if not isinstance(entries, list) or not entries or not all(isinstance(e, dict) for e in entries):
        raise IntegrityError("the record has no custody entries")
    head = GENESIS
    for seq, entry in enumerate(entries):
        if entry.get("seq") != seq:
            raise IntegrityError(f"entry {seq}: sequence number is {entry.get('seq')} (entries removed or reordered)")
        if entry.get("prev") != head:
            raise IntegrityError(f"entry {seq}: does not link to the previous entry (an entry was changed)")
        head = sha256_hex(canonical(entry))
    try:
        signed = verify_signed_heads(entries, {key_id: public})
    except (binascii.Error, ValueError):  # a signature that is not base64, a head that is not hex
        raise IntegrityError("a chain.sign entry is malformed") from None
    if signed == 0 or entries[-1].get("action") != "chain.sign":
        raise IntegrityError("the record does not end with a signed custody head (entries added or signatures removed)")
    export = entries[-2] if len(entries) > 1 else {}
    if export.get("action") != "log.export" or export.get("case_id") != record.get("case_id"):
        raise IntegrityError("the record's case id is not the one named by its signed log.export entry")
    check = LogCheck(
        case_id=str(record.get("case_id")),
        entries=len(entries),
        signed_heads=signed,
        key_id=key_id,
        key_confirmed=expected_key_id is not None,
    )
    return check, entries


def _no_constant(name: str) -> None:
    raise ValueError(f"{name} is not JSON")  # NaN and Infinity cannot be canonicalised


def load_record(path: Path) -> dict[str, Any]:
    """Read and parse a processing record (bounded; duplicate keys and NaN refused)."""
    data = read_bounded(path, MAX_RECORD_BYTES)  # size refusals stay InputRejectedError
    try:
        record = json.loads(data.decode("utf-8"), parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError):
        raise IntegrityError("the record is not valid UTF-8 JSON") from None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise IntegrityError(f"not a {SCHEMA} file")
    return record
