"""Jobs and signed job reports (PRD FR-28): list, show, export, and verify outside the store.

Jobs are read from the custody log only; the log's hash chain is verified when a case is opened.
A report is shown or exported only after three checks pass. Its bytes must match the hash in the
custody log. Its Ed25519 signature must verify against the store's examiner identity. It must
name its own job and case. An exported report is the exact canonical bytes that were signed,
with a detached base64 signature next to it (``<report>.sig``). Anyone can check the pair later
without the case store (`check_exported_report`). The key id in the report proves only that the
holder of that key signed it, so the verifier compares it with the examiner's published key id.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import rfc8785

from ridge.case.crypto import sha256_hex
from ridge.case.custody import Entry
from ridge.case.identity import key_id_for, public_identity, verify_signature
from ridge.case.jobs import REPORT_SCHEMA
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, OutputExistsError, ParameterError
from ridge.image_io import publish, read_bounded

SIGNATURE_SUFFIX = ".sig"
MAX_REPORT_BYTES = 1024 * 1024  # reports hold summaries only; real ones are a few KiB
MAX_SIGNATURE_BYTES = 1024
MIN_PREFIX = 8
_JOB_REF = re.compile(r"[0-9a-f-]{8,36}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


@dataclass(frozen=True)
class JobRecord:
    """One job as the custody log records it."""

    job_id: str
    evidence_sha256: str
    started_utc: str
    ended_utc: str | None
    result: str  # "ok", "failed", or "open" (started, never closed: the process died)
    error: str | None
    report_sha256: str | None
    key_id: str | None

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


@dataclass(frozen=True)
class SignedReport:
    """A report whose hash, signature and identity have been checked."""

    job_id: str
    canonical: bytes
    signature: bytes
    key_id: str
    report: dict[str, Any]


def list_jobs(entries: Sequence[Entry]) -> list[JobRecord]:
    """Every job in the custody log, in the order it started."""
    jobs: dict[str, dict[str, Any]] = {}
    for entry in entries:
        action, job_id = entry.get("action"), entry.get("job_id")
        if not isinstance(job_id, str):
            continue
        if action == "job.start":
            jobs[job_id] = {
                "job_id": job_id,
                "evidence_sha256": entry["sha256"],
                "started_utc": entry["ts_utc"],
                "ended_utc": None,
                "result": "open",
                "error": None,
                "report_sha256": None,
                "key_id": None,
            }
        elif job_id in jobs and action == "report.sign":
            jobs[job_id].update(report_sha256=entry["report_sha256"], key_id=entry["key_id"])
        elif job_id in jobs and action == "job.end":
            jobs[job_id].update(ended_utc=entry["ts_utc"], result=entry["result"], error=entry.get("error"))
    return [JobRecord(**job) for job in jobs.values()]


def resolve_job(entries: Sequence[Entry], ref: str) -> JobRecord:
    """Find a signed job by its id or a unique prefix of at least 8 characters.

    Only ids that the verified custody log contains ever reach a file path (no path traversal).
    """
    ref = ref.strip().lower()
    if not _JOB_REF.fullmatch(ref):
        raise ParameterError(f"a job id is a UUID or at least its first {MIN_PREFIX} characters")
    matches = [job for job in list_jobs(entries) if job.job_id.startswith(ref)]
    if not matches:
        raise ParameterError(f"no job {ref} in this case")
    if len(matches) > 1:
        raise ParameterError(f"job id {ref} is ambiguous ({len(matches)} jobs): give more characters")
    job = matches[0]
    if job.report_sha256 is None or job.key_id is None:
        raise ParameterError(f"job {job.job_id} has no signed report (result: {job.result})")
    return job


def load_report(case: OpenCase, store: Path, ref: str, *, log: bool = True) -> SignedReport:
    """Read a job's report after checking it against the custody log and the examiner identity.

    The read is logged as ``report.read`` unless `log` is False.
    """
    job = resolve_job(case.entries, ref)
    canonical, signature = case.get_report(job.job_id)
    if sha256_hex(canonical) != job.report_sha256:
        raise IntegrityError(f"report {job.job_id}: content does not match the custody log")
    key_id, public = public_identity(store)
    if job.key_id != key_id or not verify_signature(public, signature, canonical):
        raise IntegrityError(f"report {job.job_id}: signature is invalid or by an unknown key")
    report = _parse(canonical)
    if report.get("job_id") != job.job_id or report.get("case_id") != case.case_id:
        raise IntegrityError(f"report {job.job_id}: belongs to another job or case")
    if log:
        case.entries.append(case.custody.append("report.read", job_id=job.job_id))
    return SignedReport(job.job_id, canonical, signature, key_id, report)


def signature_path(report_path: Path) -> Path:
    """Where the detached signature of an exported report lives."""
    return report_path.with_name(report_path.name + SIGNATURE_SUFFIX)


def export_report(case: OpenCase, store: Path, ref: str, dest: Path, *, overwrite: bool = False) -> SignedReport:
    """Write a checked report and its detached signature in plaintext (logged as ``report.export``)."""
    signed = load_report(case, store, ref, log=False)
    sig_dest = signature_path(dest)
    if not overwrite and (dest.exists() or sig_dest.exists()):
        raise OutputExistsError(f"{dest.name} or {sig_dest.name} already exists (use --overwrite to replace)")
    publish(dest, signed.canonical, overwrite=overwrite)
    publish(sig_dest, base64.b64encode(signed.signature) + b"\n", overwrite=overwrite)
    case.entries.append(case.custody.append("report.export", job_id=signed.job_id, destination=str(dest.resolve())))
    return signed


@dataclass(frozen=True)
class ReportCheck:
    """An exported report whose signature verified."""

    job_id: str
    case_id: str
    created_utc: str
    key_id: str
    key_confirmed: bool  # True when the caller supplied the expected key id and it matched


def check_exported_report(
    report_path: Path, sig_path: Path | None = None, *, expected_key_id: str | None = None
) -> ReportCheck:
    """Verify an exported report and its detached signature without the case store."""
    canonical = read_bounded(report_path, MAX_REPORT_BYTES)
    sig_text = read_bounded(sig_path or signature_path(report_path), MAX_SIGNATURE_BYTES)
    try:
        signature = base64.b64decode(sig_text.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise IntegrityError("the signature file is not base64") from None
    report = _parse(canonical)
    if bytes(rfc8785.dumps(report)) != canonical:
        raise IntegrityError("the report is not in its signed canonical form (it was reformatted or edited)")
    signer = report.get("signer")
    if not isinstance(signer, dict):
        raise IntegrityError("the report names no signer")
    try:
        public = base64.b64decode(str(signer.get("public_key")), validate=True)
    except (binascii.Error, ValueError):
        raise IntegrityError("the signer's public key is not base64") from None
    if key_id_for(public) != signer.get("key_id"):
        raise IntegrityError("the signer's key id does not match its public key")
    if expected_key_id is not None and signer["key_id"] != expected_key_id.strip().lower():
        raise IntegrityError(f"signed by key {signer['key_id']}, not by the expected key {expected_key_id}")
    if not verify_signature(public, signature, canonical):
        raise IntegrityError("the signature does not verify: the report was changed or the signature is wrong")
    return ReportCheck(
        job_id=str(report.get("job_id")),
        case_id=str(report.get("case_id")),
        created_utc=str(report.get("created_utc")),
        key_id=str(signer["key_id"]),
        key_confirmed=expected_key_id is not None,
    )


def _parse(canonical: bytes) -> dict[str, Any]:
    try:
        report = json.loads(canonical.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise IntegrityError("the report is not valid UTF-8 JSON") from None
    if not isinstance(report, dict) or report.get("schema") != REPORT_SCHEMA:
        raise IntegrityError(f"not a {REPORT_SCHEMA} report")
    return report


# ---------------------------------------------------------------------------- text rendering
def printable(value: object) -> str:
    """`value` as text with control characters replaced (no terminal escape injection, CWE-150)."""
    return _CONTROL.sub("?", str(value))


def _yes(value: object) -> str:
    return "yes" if value else "no"


def render_report(report: dict[str, Any], key_id: str) -> str:
    """Render a verified report as plain text for the examiner (the signed JSON stays authoritative)."""
    env, source = report.get("ridge") or {}, report.get("input") or {}
    params, meas = report.get("parameters") or {}, report.get("measurements") or {}
    period = params.get("period")
    size = source.get("size_px") or ["?", "?"]
    lines = [
        f"Job report {report.get('job_id')}   signature verified (key {key_id})",
        f"Case          {report.get('case_id')}   reference {report.get('case_reference')}",
        f"Created       {report.get('created_utc')}",
        f"Ridge         {env.get('version')} on {env.get('platform')} ({env.get('machine')}), "
        f"Python {env.get('python')}",
        f"Input         {source.get('label')}   {source.get('format')} {size[0]}x{size[1]} px",
        f"              sha256 {source.get('sha256')}",
        f"Parameters    ridge spacing {'auto' if period is None else f'{period:g} px'}, "
        f"min quality {params.get('min_quality')}, flip {_yes(params.get('flip'))}, "
        f"crop {_yes(params.get('crop'))}, debug {_yes(params.get('debug'))}, "
        f"minutiae {_yes(params.get('minutiae'))}",
        f"Measured      ridge spacing {meas.get('ridge_period_px', 0):.2f} px, "
        f"finger found {_yes(meas.get('found_finger'))}, output scale {meas.get('output_scale')}",
        _export_line(report.get("export")),
        _nfiq2_line((report.get("quality") or {}).get("nfiq2")),
        _minutiae_line(report.get("minutiae")),
        "Outputs",
        *(
            f"  {o.get('role', ''):9} {o.get('sha256')}  {o.get('size', 0):>9}  {o.get('label')}"
            for o in report.get("outputs") or []
        ),
        f"Custody head  {report.get('custody_head')}",
        str(report.get("disclaimer", "")),
    ]
    return "\n".join(printable(line) for line in lines if line)


def _export_line(export: dict[str, Any] | None) -> str:
    if export is None:
        return "Export        not requested"
    if not export.get("produced"):
        return f"Export        not produced: {export.get('reason')}"
    scale = export.get("scale") or {}
    transforms = ", ".join(export.get("transforms") or []) or "none"
    return (
        f"Export        {export.get('ppi'):g} ppi, scale from {scale.get('method')} "
        f"(+-{scale.get('uncertainty_pct', 0):.1f} %), transforms: {transforms}"
    )


def _nfiq2_line(nfiq2: dict[str, Any] | None) -> str:
    if nfiq2 is None:
        return ""
    if not nfiq2.get("computed"):
        return f"NFIQ 2        not computed: {nfiq2.get('reason')}"
    return f"NFIQ 2        {nfiq2.get('score')} ({nfiq2.get('label')}; {nfiq2.get('version')})"


def _minutiae_line(minutiae: dict[str, Any] | None) -> str:
    if minutiae is None:
        return ""
    if not minutiae.get("produced"):
        return f"Minutiae      not produced: {minutiae.get('reason')}"
    return (
        f"Minutiae      {minutiae.get('count')} ({minutiae.get('endings')} endings, "
        f"{minutiae.get('bifurcations')} bifurcations), {minutiae.get('label')}"
    )
