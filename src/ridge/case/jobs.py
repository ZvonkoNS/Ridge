"""Extraction jobs inside a case, with signed JSON job reports (PRD FR-23, FR-34, architecture §7.2).

A job reads one evidence item, runs the unchanged extraction pipeline, stores the outputs as
artefacts and records a report that is enough to reproduce the job: Ridge and library
versions, platform and CPU architecture, every parameter, measurements, input and output
hashes. The report is RFC 8785 canonical JSON signed with the examiner's Ed25519 key.
"""

from __future__ import annotations

import io
import platform
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import cryptography
import cv2
import numpy as np
import PIL
import rfc8785
from PIL import Image

import ridge
from ridge.case.crypto import sha256_hex
from ridge.case.custody import utc_now
from ridge.case.export_step import ExportOptions, export_and_score, minutiae_step
from ridge.case.identity import Signer
from ridge.case.keys import b64
from ridge.case.store import OpenCase, StoredItem
from ridge.errors import ExtractionError
from ridge.image_io import ALLOWED_FORMATS, ReadLimits, decode_image, encode_image
from ridge.pipeline import extract_fingerprint

REPORT_SCHEMA = "ridge.job-report/1"
DISCLAIMER = "Image enhancement only. Ridge does not identify anyone and draws no conclusions."


@dataclass(frozen=True)
class JobParams:
    """Extraction parameters recorded in the report (defaults included)."""

    period: float | None = None
    min_quality: float = 0.25
    flip: bool = False
    crop: bool = True
    debug: bool = False
    export: ExportOptions = field(default_factory=ExportOptions)
    minutiae: bool = False

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form for the custody log and the report."""
        return {**asdict(self), "export": self.export.to_json()}


@dataclass(frozen=True)
class JobOutcome:
    """What a successful job produced."""

    job_id: str
    outputs: list[StoredItem]
    report: dict[str, Any]


def environment() -> dict[str, Any]:
    """Software and platform facts needed to reproduce a result (NFR-3: per OS and CPU architecture)."""
    return {
        "version": ridge.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "dependencies": {
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "pillow": PIL.__version__,
            "cryptography": cryptography.__version__,
        },
    }


def _probe(data: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS) as im:
        return {"format": im.format, "size_px": list(im.size)}


def run_extraction_job(
    case: OpenCase,
    evidence_sha: str,
    signer: Signer,
    params: JobParams,
    *,
    limits: ReadLimits | None = None,
    nfiq2_command: Sequence[str] | None = None,
) -> JobOutcome:
    """Run one extraction job on stored evidence; every step is in the custody log.

    Produces the print (and debug images), the comparison export (FR-30 to FR-32) and, when
    `nfiq2_command` is configured, an indicative NFIQ 2 score (FR-33).
    """
    evidence = case.item(evidence_sha)
    if evidence.role != "evidence":
        raise ExtractionError("jobs run on evidence items only")
    job_id = str(uuid.uuid4())
    case.entries.append(
        case.custody.append("job.start", job_id=job_id, sha256=evidence.sha256, parameters=params.to_json())
    )
    data = case.read(evidence.sha256, job_id=job_id)
    try:
        result = extract_fingerprint(
            decode_image(data, limits or ReadLimits()),
            period=params.period,
            min_quality=params.min_quality,
            flip=params.flip,
            crop=params.crop,
            debug=params.debug,
        )
    except ExtractionError as exc:
        case.entries.append(case.custody.append("job.end", result="failed", job_id=job_id, error=str(exc)))
        raise

    stem = evidence.label.rsplit(".", 1)[0]
    outputs = [
        case.store_artefact(
            encode_image(result.image, ".png"), role="print", label=f"{stem}_fingerprint.png", job_id=job_id
        )
    ]
    if result.debug is not None:
        for step, ext in (("region", ".jpg"), ("normalized", ".png"), ("gabor", ".png"), ("quality", ".png")):
            png = encode_image(getattr(result.debug, step), ext)
            outputs.append(case.store_artefact(png, role="debug", label=f"{stem}_debug_{step}{ext}", job_id=job_id))
    exports, export_fields = export_and_score(
        case, result, stem=stem, job_id=job_id, options=params.export, nfiq2_command=nfiq2_command
    )
    outputs.extend(exports)
    if params.minutiae:
        found, minutiae_fields = minutiae_step(
            case, result, stem=stem, job_id=job_id, export=export_fields["export"], mirrored=params.export.mirror
        )
        outputs.extend(found)
        export_fields.update(minutiae_fields)

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "job_id": job_id,
        "case_id": case.case_id,
        "case_reference": case.meta().case_reference,
        "created_utc": utc_now(),
        "ridge": environment(),
        "input": {"sha256": evidence.sha256, "label": evidence.label, **_probe(data)},
        "parameters": params.to_json(),
        "measurements": {
            "ridge_period_px": result.period,
            "found_finger": result.found_finger,
            "output_scale": result.output_scale,
        },
        **export_fields,
        "outputs": [{"role": o.role, "label": o.label, "sha256": o.sha256, "size": o.size} for o in outputs],
        "custody_head": case.custody.head,
        "signer": {"key_id": signer.key_id, "public_key": b64(signer.public_key)},
        "disclaimer": DISCLAIMER,
    }
    canonical = bytes(rfc8785.dumps(report))
    case.put_report(job_id, canonical, signer.sign(canonical))
    case.entries.append(
        case.custody.append("report.sign", job_id=job_id, report_sha256=sha256_hex(canonical), key_id=signer.key_id)
    )
    case.entries.append(case.custody.append("job.end", job_id=job_id))
    case.entries.append(case.custody.sign_head(signer))
    return JobOutcome(job_id, outputs, report)
