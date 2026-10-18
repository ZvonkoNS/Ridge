"""Disclosure package: a case's signed records in one new folder, verifiable offline (PRIV-3, FR-28).

``ridge-case package CASE --to DIR`` creates DIR and writes

- ``processing-record.json``: the signed custody log, as ``ridge-case log --to`` writes it, and
  ``processing-record.html``, its readable copy;
- ``reports/<job-id>.json`` and ``.json.sig``: every signed job report, exactly as signed;
- ``reports/<job-id>.html``: a readable copy of each report with the job's examiner notes (not
  signed itself, but listed with its hash in the signed manifest);
- ``MANIFEST.json`` and ``MANIFEST.json.sig``: every file's SHA-256 and size, RFC 8785
  canonical, signed with the examiner key.

The package holds no images. Reports name the SHA-256 of every input and output, so images
exported one by one (``ridge-case export``, each logged) can be matched to them. The export is
logged as ``package.export`` with the package id and the jobs it holds before the processing
record is signed, so the record names its own package. `check_package` verifies the manifest
signature, every file, that nothing was added or removed, the processing record, every report
signature, and that each report is the one the custody log signed.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rfc8785

import ridge
from ridge.case.crypto import sha256_hex
from ridge.case.custody import utc_now
from ridge.case.identity import Signer, key_id_for, public_identity, verify_signature
from ridge.case.keys import b64
from ridge.case.notes import list_notes
from ridge.case.processing_record import export_log, load_record, verify_record
from ridge.case.record_html import write_record_html
from ridge.case.report_html import render_report_html
from ridge.case.reports import check_exported_report, list_jobs, load_report
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, OutputExistsError, RidgeError
from ridge.image_io import publish, read_bounded

SCHEMA = "ridge.package/1"
MANIFEST, RECORD, RECORD_HTML = "MANIFEST.json", "processing-record.json", "processing-record.html"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
_REPORT_PATH = re.compile(r"reports/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(json(\.sig)?|html)")
NOTE = "Disclosure package of a Ridge case. Verify with `ridge-case check-package`. It contains no images."


def export_package(case: OpenCase, store: Path, signer: Signer, dest: Path) -> dict[str, Any]:
    """Create `dest` (it must not exist) and write the package; return the signed manifest."""
    key_id, public = public_identity(store)
    if signer.key_id != key_id:
        raise IntegrityError("the unlocked identity is not this store's examiner identity")
    try:
        dest.mkdir()  # atomic: an existing folder is never written into
    except FileExistsError:
        raise OutputExistsError(f"{dest.name} already exists: choose a new folder name") from None
    (dest / "reports").mkdir()
    package_id = str(uuid.uuid4())
    jobs = [j.job_id for j in list_jobs(case.entries) if j.report_sha256]
    case.entries.append(
        case.custody.append("package.export", package_id=package_id, destination=str(dest.resolve()), jobs=jobs)
    )
    try:
        for job_id in jobs:
            signed = load_report(case, store, job_id, log=False)  # checked against the log and the identity
            publish(dest / "reports" / f"{job_id}.json", signed.canonical)
            publish(dest / "reports" / f"{job_id}.json.sig", base64.b64encode(signed.signature) + b"\n")
            readable = render_report_html(signed, list_notes(case.entries, job_id=job_id))
            publish(dest / "reports" / f"{job_id}.html", readable.encode("utf-8"))
        export_log(case, store, signer, dest / RECORD)
        write_record_html(dest / RECORD, dest / RECORD_HTML)  # verified first, like any reviewer would
        manifest = _manifest_for(dest, package_id, case.case_id, key_id, public)
        canonical = bytes(rfc8785.dumps(manifest))
        publish(dest / MANIFEST, canonical)
        publish(dest / (MANIFEST + ".sig"), base64.b64encode(signer.sign(canonical)) + b"\n")
    except (OSError, RidgeError) as exc:  # the folder stays incomplete and fails check-package
        case.entries.append(
            case.custody.append("package.export", result="failed", package_id=package_id, error=type(exc).__name__)
        )
        raise
    return manifest


def _manifest_for(dest: Path, package_id: str, case_id: str, key_id: str, public: bytes) -> dict[str, Any]:
    files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    return {
        "schema": SCHEMA,
        "package_id": package_id,
        "case_id": case_id,
        "created_utc": utc_now(),
        "ridge_version": ridge.__version__,
        "identity": {"key_id": key_id, "public_key": b64(public)},
        "note": NOTE,
        "files": [_describe(dest, f) for f in files],
    }


def _describe(root: Path, name: str) -> dict[str, Any]:
    data = (root / name).read_bytes()
    return {"path": name, "sha256": sha256_hex(data), "size": len(data)}


@dataclass(frozen=True)
class PackageCheck:
    """A package whose every check passed."""

    package_id: str
    case_id: str
    reports: int
    record_entries: int
    key_id: str
    key_confirmed: bool
    created_utc: str = ""  # from the signed manifest: the signer's clock


def _manifest(root: Path, expected_key_id: str | None) -> tuple[dict[str, Any], str, bytes]:
    if not (root / MANIFEST).is_file() or not (root / (MANIFEST + ".sig")).is_file():
        raise IntegrityError(f"{root.name} has no signed {MANIFEST}: not a complete Ridge package")
    canonical = read_bounded(root / MANIFEST, MAX_MANIFEST_BYTES)
    try:
        manifest = json.loads(canonical.decode("utf-8"))
        signature = base64.b64decode(read_bounded(root / (MANIFEST + ".sig"), 1024).strip(), validate=True)
        public = base64.b64decode(str(manifest["identity"]["public_key"]), validate=True)
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, binascii.Error):
        raise IntegrityError("the manifest or its signature is malformed") from None
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise IntegrityError(f"not a {SCHEMA} package")
    if bytes(rfc8785.dumps(manifest)) != canonical:
        raise IntegrityError("the manifest is not in its signed canonical form (it was edited)")
    key_id = key_id_for(public)
    if manifest["identity"].get("key_id") != key_id:
        raise IntegrityError("the manifest's key id does not match its public key")
    if expected_key_id is not None and key_id != expected_key_id.strip().lower():
        raise IntegrityError(f"the package is signed with key {key_id}, not {expected_key_id}")
    if not verify_signature(public, signature, canonical):
        raise IntegrityError("the manifest signature does not verify: the package was changed")
    return manifest, key_id, public


def _check_files(root: Path, listed: list[Any]) -> None:
    names = [f["path"] for f in listed if isinstance(f, dict) and isinstance(f.get("path"), str)]
    if len(names) != len(listed) or len(set(names)) != len(names):
        raise IntegrityError("the manifest lists a file twice or malformed entries")
    for name in names:
        if name not in (RECORD, RECORD_HTML) and not _REPORT_PATH.fullmatch(name):
            raise IntegrityError(f"the manifest names an unexpected file: {name!r}")
    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    extra = present - set(names) - {MANIFEST, MANIFEST + ".sig"}
    missing = set(names) - present
    if extra or missing:
        raise IntegrityError(f"files added {sorted(extra)} or removed {sorted(missing)} after signing")
    for entry in listed:
        path = root / entry["path"]
        if path.is_symlink():
            raise IntegrityError(f"{entry['path']} is a link")
        data = read_bounded(path, MAX_FILE_BYTES)
        if sha256_hex(data) != entry.get("sha256") or len(data) != entry.get("size"):
            raise IntegrityError(f"{entry['path']} was changed after signing")


def check_package(root: Path, *, expected_key_id: str | None = None) -> PackageCheck:
    """Verify a disclosure package offline; IntegrityError names the first problem."""
    manifest, key_id, _ = _manifest(root, expected_key_id)
    files = manifest.get("files")
    if not isinstance(files, list):
        raise IntegrityError("the manifest lists no files")
    _check_files(root, files)
    record_check, entries = verify_record(load_record(root / RECORD), expected_key_id=key_id)
    if record_check.case_id != manifest.get("case_id"):
        raise IntegrityError("the processing record belongs to another case")
    exported = [e for e in entries if e.get("action") == "package.export"]
    mine = next((e for e in exported if e.get("package_id") == manifest.get("package_id")), None)
    reports = sorted(f["path"] for f in files if f["path"].endswith(".json") and f["path"] != RECORD)
    job_ids = [Path(p).stem for p in reports]
    if mine is None or sorted(mine.get("jobs") or []) != job_ids:
        raise IntegrityError("the processing record does not name this package and its reports")
    readable = [Path(f["path"]).stem for f in files if f["path"].startswith("reports/") and f["path"].endswith(".html")]
    if any(job_id not in job_ids for job_id in readable):
        raise IntegrityError("a readable copy has no signed report in this package")
    signed = {j.job_id: j.report_sha256 for j in list_jobs(entries)}
    for path, job_id in zip(reports, job_ids, strict=True):
        report = check_exported_report(root / path, expected_key_id=key_id)
        if report.job_id != job_id or report.case_id != record_check.case_id:
            raise IntegrityError(f"{path} belongs to another job or case")
        if sha256_hex((root / path).read_bytes()) != signed.get(job_id):
            raise IntegrityError(f"{path} is not the report the custody log signed")
    return PackageCheck(
        package_id=str(manifest.get("package_id")),
        case_id=record_check.case_id,
        reports=len(reports),
        record_entries=record_check.entries,
        key_id=key_id,
        key_confirmed=expected_key_id is not None,
        created_utc=str(manifest.get("created_utc", "")),
    )
