"""Case verification (PRD FR-24): hashes, custody chain, report and head signatures, stray files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ridge.case.case_model import ROLES
from ridge.case.crypto import sha256_hex
from ridge.case.custody import Entry, verify_signed_heads
from ridge.case.identity import public_identity, verify_signature
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError


@dataclass
class VerifyResult:
    """Outcome of `verify_case`; `problems` lists every failure precisely."""

    entries: int = 0
    items: int = 0
    reports: int = 0
    signed_heads: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing failed."""
        return not self.problems


def unsigned_jobs(entries: list[Entry]) -> list[str]:
    """Completed jobs that no later signed head covers (e.g. a stripped ``chain.sign`` line)."""
    last_signed = max((i for i, e in enumerate(entries) if e["action"] == "chain.sign"), default=-1)
    return [
        f"job {e['job_id']}: completed but not covered by a signed custody head (entries may have been removed)"
        for i, e in enumerate(entries)
        if e["action"] == "job.end" and e["result"] == "ok" and i > last_signed
    ]


def verify_case(case: OpenCase, store: Path) -> VerifyResult:
    """Verify everything in an open case (the custody chain was already verified when it was opened)."""
    result = VerifyResult(entries=len(case.entries))
    key_id, public = public_identity(store)
    keys = {key_id: public}

    expected_files: set[Path] = set()
    for item in case.items():
        path = case.blob_path(item.role, item.sha256)
        expected_files.add(path.resolve())
        try:
            case.read(item.sha256, log=False)
        except (IntegrityError, OSError) as exc:
            result.problems.append(f"{item.role} {item.sha256[:12]} ({item.label}): {exc}")
        result.items += 1

    for entry in case.entries:
        if entry["action"] != "report.sign":
            continue
        job_id = entry["job_id"]
        report_path, sig_path = case.report_paths(job_id)
        expected_files.update({report_path.resolve(), sig_path.resolve()})
        try:
            canonical, signature = case.get_report(job_id)
        except (IntegrityError, OSError) as exc:
            result.problems.append(f"report {job_id}: {exc}")
            continue
        if sha256_hex(canonical) != entry["report_sha256"]:
            result.problems.append(f"report {job_id}: content does not match the custody log")
        signer_key = keys.get(entry["key_id"])
        if signer_key is None or not verify_signature(signer_key, signature, canonical):
            result.problems.append(f"report {job_id}: signature is invalid or by an unknown key")
        result.reports += 1

    try:
        result.signed_heads = verify_signed_heads(case.entries, keys)
    except IntegrityError as exc:
        result.problems.append(str(exc))
    result.problems.extend(unsigned_jobs(case.entries))

    for folder in {*ROLES.values(), "reports"}:
        for path in sorted((case.dir / folder).glob("*")) if (case.dir / folder).is_dir() else []:
            if path.resolve() not in expected_files:
                result.problems.append(f"unexpected file not in the custody log: {folder}/{path.name}")

    case.entries.append(
        case.custody.append(
            "case.verify", result="ok" if result.ok else "failed", problems=len(result.problems), checked=result.items
        )
    )
    return result
