"""Signed custody heads for out-of-band countersigning (PRD OQ-8, risk R-5).

An offline log cannot show that entries were cut off its end after the last signed head held
elsewhere. ``export_head`` writes a small signed file (no images, no personal data: case id,
sequence number, chain hash, time, key) that the laboratory can countersign or timestamp in
its own systems. ``check_head`` verifies such a file, and with a later processing record it
proves the record still contains that exact head: a log truncated or rewritten before the head
no longer matches it, which the record alone cannot reveal.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rfc8785

from ridge.case.custody import utc_now
from ridge.case.identity import Signer, key_id_for, public_identity, verify_signature
from ridge.case.keys import b64, unb64
from ridge.case.processing_record import MAX_RECORD_BYTES, check_exported_log
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, OutputExistsError
from ridge.image_io import publish, read_bounded

SCHEMA = "ridge.custody-head/1"
MAX_HEAD_BYTES = 16 * 1024
_FIELDS = {"schema", "case_id", "seq", "head", "ts_utc", "exported_utc", "key_id", "public_key", "signature"}
# `signature` is the custody log's own chain.sign signature over the head hash (so a record can be
# matched); `file_signature` signs the whole file, binding the case id and sequence number to it.
_ALL_FIELDS = {*_FIELDS, "file_signature"}


def export_head(case: OpenCase, store: Path, signer: Signer, dest: Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Log the export, sign the custody head, and write it to `dest` (canonical JSON)."""
    if not overwrite and dest.exists():
        raise OutputExistsError(f"{dest.name} already exists (use --overwrite to replace)")
    key_id, public = public_identity(store)
    if signer.key_id != key_id:
        raise IntegrityError("the unlocked identity is not this store's examiner identity")
    case.entries.append(case.custody.append("head.export", destination=str(dest.resolve()), case_id=case.case_id))
    signed = case.custody.sign_head(signer)
    case.entries.append(signed)
    doc = {
        "schema": SCHEMA,
        "case_id": case.case_id,
        "seq": signed["seq"],
        "head": signed["head"],
        "ts_utc": signed["ts_utc"],
        "exported_utc": utc_now(),
        "key_id": key_id,
        "public_key": b64(public),
        "signature": signed["signature"],
    }
    doc["file_signature"] = base64.b64encode(signer.sign(bytes(rfc8785.dumps(doc)))).decode("ascii")
    try:
        publish(dest, bytes(rfc8785.dumps(doc)), overwrite=overwrite)
    except (OSError, OutputExistsError) as exc:
        case.entries.append(case.custody.append("head.export", result="failed", error=type(exc).__name__))
        raise
    return doc


@dataclass(frozen=True)
class HeadCheck:
    """A verified custody head, and whether a record was checked against it."""

    case_id: str
    seq: int
    key_id: str
    key_confirmed: bool
    record_entries: int | None


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(read_bounded(path, MAX_HEAD_BYTES).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise IntegrityError("the custody head is not a JSON document") from None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or set(doc) != _ALL_FIELDS:
        raise IntegrityError(f"the custody head is not a {SCHEMA} document")
    if not isinstance(doc["seq"], int) or isinstance(doc["seq"], bool) or doc["seq"] < 0:
        raise IntegrityError("the custody head has an invalid sequence number")
    return doc


def check_head(path: Path, *, record: Path | None = None, expected_key_id: str | None = None) -> HeadCheck:
    """Verify a custody head; with `record`, require that the record contains exactly that head."""
    doc = _load(path)
    try:
        public = unb64(str(doc["public_key"]))
        signature = base64.b64decode(str(doc["signature"]), validate=True)
        file_signature = base64.b64decode(str(doc["file_signature"]), validate=True)
        head = bytes.fromhex(str(doc["head"]))
    except (binascii.Error, ValueError):
        raise IntegrityError("the custody head has malformed fields") from None
    if key_id_for(public) != doc["key_id"]:
        raise IntegrityError("the custody head's key id does not match its public key")
    if expected_key_id is not None and doc["key_id"] != expected_key_id:
        raise IntegrityError(f"the custody head is signed by key {doc['key_id']}, not {expected_key_id}")
    if len(head) != 32 or not verify_signature(public, signature, head):
        raise IntegrityError("the custody head's signature does not verify")
    body = bytes(rfc8785.dumps({k: v for k, v in doc.items() if k != "file_signature"}))
    if not verify_signature(public, file_signature, body):
        raise IntegrityError("the custody head file was changed after it was signed")
    entries: int | None = None
    if record is not None:
        entries = _check_record(doc, record)
    return HeadCheck(doc["case_id"], doc["seq"], doc["key_id"], expected_key_id is not None, entries)


def _check_record(doc: dict[str, Any], record: Path) -> int:
    checked = check_exported_log(record, expected_key_id=doc["key_id"])
    if checked.case_id != doc["case_id"]:
        raise IntegrityError("the processing record belongs to another case")
    entries = json.loads(read_bounded(record, MAX_RECORD_BYTES).decode("utf-8"))["entries"]
    if doc["seq"] >= len(entries):
        raise IntegrityError(
            f"the processing record ends at entry {len(entries) - 1}, before the countersigned head "
            f"(entry {doc['seq']}): it is older than the head, or entries were removed"
        )
    entry = entries[doc["seq"]]
    same = entry.get("head") == doc["head"] and entry.get("signature") == doc["signature"]
    if entry.get("action") != "chain.sign" or not same:
        raise IntegrityError(
            f"entry {doc['seq']} of the processing record is not the countersigned head: "
            "the custody log was rewritten or truncated and continued after the head was exported"
        )
    return checked.entries
