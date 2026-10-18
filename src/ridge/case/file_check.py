"""Check an exported file without a case store: the GUI's "Check exported files".

Reviewers, the DPO and the FQM receive reports, processing records, custody heads, packages, key
cards, key registers and limits files. The kind is read from the file's schema (a folder is a
disclosure package) and each kind goes to the verifier the CLI uses, so the GUI and the CLI
cannot disagree. With a key register the signer's holder is named and checked. Nothing is
written and no case store is needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ridge.case.custody_head import SCHEMA as HEAD_SCHEMA
from ridge.case.custody_head import check_head
from ridge.case.jobs import REPORT_SCHEMA
from ridge.case.key_card import CARD_SCHEMA, check_card
from ridge.case.key_register import SCHEMA as REGISTER_SCHEMA
from ridge.case.key_register import confirm_key, describe, load_register
from ridge.case.limits import SCHEMA as LIMITS_SCHEMA
from ridge.case.limits import read_limits
from ridge.case.package import check_package
from ridge.case.processing_record import MAX_RECORD_BYTES, check_exported_log
from ridge.case.processing_record import SCHEMA as RECORD_SCHEMA
from ridge.case.reports import check_exported_report
from ridge.errors import IntegrityError, ParameterError
from ridge.image_io import read_bounded


@dataclass
class FileCheck:
    """What was checked and what it showed; every line is safe to display."""

    kind: str
    title: str
    details: list[str] = field(default_factory=list)
    key_id: str | None = None
    role: str | None = None
    signed_utc: str | None = None
    holder: str | None = None
    claimed_holder: str | None = None  # a key card's own claim, checked against a register

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return {k: v for k, v in self.__dict__.items() if k not in ("role", "signed_utc", "claimed_holder")}


def _schema(path: Path) -> str:
    try:
        doc = json.loads(read_bounded(path, MAX_RECORD_BYTES).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ParameterError("this is not a Ridge file (not JSON)") from None
    schema = doc.get("schema") if isinstance(doc, dict) else None
    if not isinstance(schema, str):
        raise ParameterError("this is not a Ridge file (no schema)")
    return schema


def _report(path: Path) -> FileCheck:
    c = check_exported_report(path)
    lines = [f"Job {c.job_id}, case {c.case_id}", f"Created {c.created_utc}; the signature verifies"]
    return FileCheck("report", "Signed job report", lines, c.key_id, "examiner", c.created_utc)


def _record(path: Path) -> FileCheck:
    c = check_exported_log(path)
    lines = [f"Case {c.case_id}: {c.entries} entries, {c.signed_heads} signed head(s), chain intact"]
    return FileCheck("record", "Processing record", lines, c.key_id, "examiner", c.exported_utc)


def _head(path: Path) -> FileCheck:
    c = check_head(path)
    lines = [f"Case {c.case_id}, entry {c.seq}, signed {c.signed_utc}"]
    return FileCheck("head", "Custody head", lines, c.key_id, "examiner", c.signed_utc)


def _card(path: Path) -> FileCheck:
    c = check_card(path)
    lines = [f"{c.role} key of {c.holder}, made {c.created_utc}", "The card was signed with its own key (possession)"]
    result = FileCheck("card", "Key card", lines, c.key_id, c.role, c.created_utc)
    result.claimed_holder = c.holder
    return result


def _register(path: Path) -> FileCheck:
    r = load_register(path)
    lines = [f"{r.laboratory}: {len(r.keys)} key(s), sha256 {r.sha256[:16]}"]
    lines += [
        f"{k.role} {k.key_id} {k.holder}{', revoked ' + str(k.revoked) if k.revoked else ''}" for k in r.keys.values()
    ]
    return FileCheck("register", "Key register", lines[:51])


def _limits(path: Path) -> FileCheck:
    limits = read_limits(path)
    signer = limits.signed_by["key_id"] if limits.signed_by else None
    lines = [
        f"From {limits.source}, sha256 {limits.sha256[:16]}",
        "Signed by the FQM key below" if signer else "Not signed",
    ]
    now = datetime.now(UTC).isoformat()
    return FileCheck("limits", "Limits of use", lines, signer, "fqm" if signer else None, now if signer else None)


_BY_SCHEMA = {
    REPORT_SCHEMA: _report,
    RECORD_SCHEMA: _record,
    HEAD_SCHEMA: _head,
    CARD_SCHEMA: _card,
    REGISTER_SCHEMA: _register,
    LIMITS_SCHEMA: _limits,
}


def check_exported(path: Path, register: Path | None = None) -> FileCheck:
    """Verify one exported file or package folder; with `register`, name and check the signer."""
    if path.is_dir():
        c = check_package(path)
        lines = [f"Case {c.case_id}: {c.reports} report(s), processing record with {c.record_entries} entries"]
        result = FileCheck("package", "Disclosure package", lines, c.key_id, "examiner", c.created_utc)
    else:
        check = _BY_SCHEMA.get(_schema(path))
        if check is None:
            raise ParameterError("this Ridge file cannot be checked here")
        result = check(path)
    if register is not None and result.key_id and result.role and result.signed_utc:
        reg = load_register(register)
        key = confirm_key(reg, result.key_id, result.role, result.signed_utc)
        if result.claimed_holder is not None and result.claimed_holder != key.holder:
            raise IntegrityError(f"the card names {result.claimed_holder!r}; the register lists {key.holder!r}")
        result.holder = key.holder
        result.details.append(f"Key {result.key_id} {describe(reg, key)}")
    elif result.key_id and result.role:
        result.details.append(f"Signed with key {result.key_id}: confirm it with the laboratory's key register")
    return result
