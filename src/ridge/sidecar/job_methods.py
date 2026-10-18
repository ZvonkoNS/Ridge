"""Sidecar methods for jobs and records: run, list, reports, reproduction, processing record, comparison."""

from __future__ import annotations

import json
from typing import cast

from ridge.case.compare import SHEET_PPI, export_sheet
from ridge.case.custody_head import export_head
from ridge.case.export_step import ExportOptions
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.package import export_package
from ridge.case.processing_record import export_log
from ridge.case.report_html import export_report_html
from ridge.case.reports import export_report, list_jobs, load_report, signature_path
from ridge.case.reproduce import reproduce_job
from ridge.errors import ParameterError
from ridge.sidecar.protocol import Json
from ridge.sidecar.session import Session, absolute, item_json

NUMBER = (int, float)
LOG_PAGE_MAX = 500


def _roi(value: Json) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if len(value) != 4 or not all(type(v) is int for v in value):
        raise ParameterError("roi must be [x, y, width, height] in whole pixels")
    return (value[0], value[1], value[2], value[3])


def _ruler(value: Json) -> tuple[float, float, float, float, float] | None:
    if value is None:
        return None
    if len(value) != 5 or not all(isinstance(v, NUMBER) and not isinstance(v, bool) for v in value):
        raise ParameterError("ruler must be [x1, y1, x2, y2, millimetres]")
    return cast(tuple[float, float, float, float, float], tuple(float(v) for v in value))


def run_job(session: Session, params: dict[str, Json]) -> Json:
    """Run one extraction job; returns the outputs and the report's summary fields."""
    case, signer = session.require()
    export = ExportOptions(
        enabled=params.get("export", True),
        mirror=params.get("mirror", True),
        target_ppi=float(params.get("ppi", 500.0)),
        ruler=_ruler(params.get("ruler")),
    )
    job = JobParams(
        period=params.get("period"),
        min_quality=float(params.get("min_quality", 0.25)),
        flip=params.get("flip", False),
        crop=params.get("crop", True),
        debug=params.get("debug", False),
        export=export,
        minutiae=params.get("minutiae", False),
        roi=_roi(params.get("roi")),
    )
    outcome = run_extraction_job(case, params["evidence"], signer, job)
    report = outcome.report
    summary = {key: report.get(key) for key in ("measurements", "export", "quality", "minutiae", "limits_of_use")}
    return {"job_id": outcome.job_id, "outputs": [item_json(o) for o in outcome.outputs], **summary}


def jobs(session: Session, params: dict[str, Json]) -> Json:
    """Jobs recorded in the custody log."""
    case, _ = session.require()
    return [job.to_json() for job in list_jobs(case.entries)]


def report(session: Session, params: dict[str, Json]) -> Json:
    """Return a job's report once its hash and signature verify (the read is logged)."""
    case, _ = session.require()
    signed = load_report(case, session.require_store(), params["job_id"])
    return {"job_id": signed.job_id, "key_id": signed.key_id, "verified": True, "report": signed.report}


def reproduce(session: Session, params: dict[str, Json]) -> Json:
    """Re-run a signed job from its report and compare every output (logged and signed)."""
    case, signer = session.require()
    result = reproduce_job(case, session.require_store(), signer, params["job_id"])
    return {
        "identical": result.identical,
        "original_job": result.original_job,
        "new_job": result.new_job,
        "matched": result.matched,
        "differing": result.differing,
        "missing": result.missing,
        "extra": result.extra,
        "environment_changes": result.environment_changes,
    }


def report_export(session: Session, params: dict[str, Json]) -> Json:
    """Export a verified report and its detached signature to a native-dialog path (logged)."""
    case, _ = session.require()
    dest = absolute(params["dest"], "dest")
    signed = export_report(
        case, session.require_store(), params["job_id"], dest, overwrite=params.get("overwrite", False)
    )
    return {"exported": str(dest), "signature": str(signature_path(dest)), "key_id": signed.key_id}


def report_export_html(session: Session, params: dict[str, Json]) -> Json:
    """Write a readable HTML rendering of a verified report to a native-dialog path (logged; not signed)."""
    case, _ = session.require()
    dest = absolute(params["dest"], "dest")
    signed = export_report_html(
        case, session.require_store(), params["job_id"], dest, overwrite=params.get("overwrite", False)
    )
    return {"exported": str(dest), "job_id": signed.job_id}


def log_entries(session: Session, params: dict[str, Json]) -> Json:
    """Return a page of the custody log, newest first, optionally one kind of action or matching text (read only).

    The hash chain was verified when the case was opened; entries hold no image data.
    """
    case, _ = session.require()
    offset, limit = params.get("offset", 0), params.get("limit", 100)
    if not (0 <= offset <= 10_000_000 and 1 <= limit <= LOG_PAGE_MAX):
        raise ParameterError(f"offset must be 0 or more and limit 1-{LOG_PAGE_MAX}")
    kind, text = params.get("action"), params.get("text")
    if text is not None and not 1 <= len(text) <= 100:
        raise ParameterError("search text must be 1-100 characters")
    needle = text.casefold() if text else None
    entries = [
        e
        for e in case.entries
        if (kind is None or e["action"] == kind or e["action"].startswith(f"{kind}."))
        and (needle is None or needle in json.dumps(e, ensure_ascii=False).casefold())
    ]
    return {"total": len(entries), "entries": entries[::-1][offset : offset + limit]}


def log_export(session: Session, params: dict[str, Json]) -> Json:
    """Export the signed processing record (custody log) to a native-dialog path (logged)."""
    case, signer = session.require()
    dest = absolute(params["dest"], "dest")
    count = export_log(case, session.require_store(), signer, dest, overwrite=params.get("overwrite", False))
    return {"exported": str(dest), "entries": count, "key_id": signer.key_id}


def head_export(session: Session, params: dict[str, Json]) -> Json:
    """Export the signed custody head for out-of-band countersigning to a native-dialog path (logged)."""
    case, signer = session.require()
    dest = absolute(params["dest"], "dest")
    doc = export_head(case, session.require_store(), signer, dest, overwrite=params.get("overwrite", False))
    return {"exported": str(dest), "seq": doc["seq"], "head": doc["head"], "key_id": doc["key_id"]}


def package_export(session: Session, params: dict[str, Json]) -> Json:
    """Write a disclosure package (signed records, no images) to a new native-dialog folder (logged)."""
    case, signer = session.require()
    dest = absolute(params["dest"], "dest")
    manifest = export_package(case, session.require_store(), signer, dest)
    reports = [f for f in manifest["files"] if f["path"].startswith("reports/") and f["path"].endswith(".json")]
    return {
        "exported": str(dest),
        "package_id": manifest["package_id"],
        "reports": len(reports),
        "key_id": signer.key_id,
    }


def compare_export(session: Session, params: dict[str, Json]) -> Json:
    """Write a side-by-side sheet of an export and a reference to a native-dialog path (logged)."""
    case, _ = session.require()
    dest = absolute(params["dest"], "dest")
    sheet = export_sheet(
        case,
        params["export"],
        params["reference"],
        dest,
        reference_ppi=params.get("reference_ppi"),
        ppi=params.get("ppi", SHEET_PPI),
        overwrite=params.get("overwrite", False),
    )
    return {
        "exported": str(dest),
        "sha256": sheet.sha256,
        "ppi": sheet.ppi,
        "reference_ppi": sheet.reference_ppi,
        "reference_ppi_source": sheet.reference_ppi_source,
    }
