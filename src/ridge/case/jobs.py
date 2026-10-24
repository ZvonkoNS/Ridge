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
from ridge.arrays import ImageU8
from ridge.build_info import source_commit
from ridge.case.case_model import StoredItem
from ridge.case.crypto import sha256_hex
from ridge.case.custody import utc_now
from ridge.case.export_step import ExportOptions, export_and_score, minutiae_step, validate_job_settings
from ridge.case.identity import Signer
from ridge.case.keys import b64
from ridge.case.limits import LimitsOfUse, load_limits, report_section
from ridge.case.store import OpenCase
from ridge.case.submission import Submission, submission_record
from ridge.errors import ExtractionError, ParameterError, RidgeError
from ridge.image_io import ALLOWED_FORMATS, ReadLimits, decode_image, encode_image
from ridge.metadata import read_metadata
from ridge.metadata.provenance import provenance_hints
from ridge.pipeline import ExtractionResult, MethodOptions, extract_fingerprint

REPORT_SCHEMA = "ridge.job-report/1"
MIN_ROI_SIDE = 32  # the smallest photo Ridge accepts (FR-9)
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
    roi: tuple[int, int, int, int] | None = None  # x, y, width, height in the EXIF-oriented photo
    finger_position: int = 0  # ANSI/NIST-ITL finger code stated by the examiner, 0 = unknown (FR-38)
    source_agency: str | None = None  # submitting agency as stated by the examiner (FR-38)
    options: MethodOptions = field(default_factory=MethodOptions)  # opt-in method variants (ADR-014)

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form for the custody log and the report."""
        return {
            **asdict(self),
            "export": self.export.to_json(),
            "roi": None if self.roi is None else list(self.roi),
            "options": self.options.to_json(),
        }

    def submission(self) -> Submission:
        """Return the validated submission statements (raises ParameterError for a bad code or text)."""
        return Submission(self.finger_position, self.source_agency)


def validate_roi(roi: object) -> None:
    """Refuse a malformed region of interest before a job starts (raises ParameterError)."""
    if roi is None:
        return
    if not isinstance(roi, tuple) or len(roi) != 4 or not all(type(v) is int for v in roi):
        raise ParameterError("roi needs four whole numbers: x, y, width, height")
    x, y, w, h = roi
    if x < 0 or y < 0 or w < MIN_ROI_SIDE or h < MIN_ROI_SIDE:
        raise ParameterError(f"roi must start inside the photo and be at least {MIN_ROI_SIDE} x {MIN_ROI_SIDE} px")


def apply_roi(image: ImageU8, roi: tuple[int, int, int, int] | None) -> ImageU8:
    """Cut the region of interest out of the decoded photo; it must lie inside the photo."""
    if roi is None:
        return image
    x, y, w, h = roi
    height, width = image.shape[:2]
    if x + w > width or y + h > height:
        raise ParameterError(f"roi {x},{y} {w}x{h} lies outside the {width}x{height} photo")
    return np.ascontiguousarray(image[y : y + h, x : x + w])


def print_area(result: ExtractionResult, roi: tuple[int, int, int, int] | None) -> dict[str, Any] | None:
    """Where the print came from, in the photo's pixels after EXIF orientation (the space of roi and ruler)."""
    if result.location is None:
        return None
    return (result.location if roi is None else result.location.shifted(roi[0], roi[1])).to_json()


def check_ruler(options: ExportOptions, photo: ImageU8) -> None:
    """Refuse ruler points that do not lie on the decoded photo (the space of `ruler`, before any roi)."""
    if not options.enabled or options.ruler is None:
        return
    height, width = photo.shape[:2]
    x1, y1, x2, y2, _ = options.ruler
    for x, y in ((x1, y1), (x2, y2)):
        if not (0 <= x <= width and 0 <= y <= height):
            raise ParameterError(f"ruler point {x:g},{y:g} lies outside the {width}x{height} photo")


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
        **source_commit(),  # commit and commit_source (FR-34)
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


def _probe(data: bytes, decoded: ImageU8) -> dict[str, Any]:
    """Format, size and metadata of the input; the size is after EXIF orientation, the space of `roi` and `ruler`.

    The metadata is read from the same verified bytes as the pixels and recorded as text only
    (FR-36), with the provenance hints drawn from it and the encoding (FR-42); the output images
    never carry any of it (FR-12).
    """
    with Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS) as im:
        probed: dict[str, Any] = {"format": im.format, "size_px": [decoded.shape[1], decoded.shape[0]]}
    metadata = read_metadata(data)
    return {**probed, "metadata": metadata, "provenance": provenance_hints(data, metadata)}


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
    validate_job_settings(params.export, nfiq2_command)  # nothing is logged or stored for invalid settings
    validate_roi(params.roi)
    submission = params.submission()
    limits_of_use = load_limits(case.dir.parent)  # a malformed limits file stops the job before it starts
    job_id = str(uuid.uuid4())
    case.entries.append(
        case.custody.append(
            "job.start",
            job_id=job_id,
            sha256=evidence.sha256,
            parameters=params.to_json(),
            limits_of_use=limits_of_use.sha256 if limits_of_use else None,
        )
    )
    try:
        return _execute(
            case,
            evidence,
            job_id=job_id,
            signer=signer,
            params=params,
            limits=limits or ReadLimits(),
            nfiq2_command=nfiq2_command,
            limits_of_use=limits_of_use,
            submission=submission,
        )
    except BaseException as exc:  # every started job is closed in the custody log
        error = str(exc) if isinstance(exc, RidgeError) else f"internal error ({type(exc).__name__})"
        case.entries.append(case.custody.append("job.end", result="failed", job_id=job_id, error=error))
        raise


def _execute(
    case: OpenCase,
    evidence: StoredItem,
    *,
    job_id: str,
    signer: Signer,
    params: JobParams,
    limits: ReadLimits,
    nfiq2_command: Sequence[str] | None,
    limits_of_use: LimitsOfUse | None,
    submission: Submission,
) -> JobOutcome:
    data = case.read(evidence.sha256, job_id=job_id)
    photo = decode_image(data, limits)  # EXIF orientation applied: the coordinate space of roi and ruler
    check_ruler(params.export, photo)  # a point off the photo would calibrate the export wrongly
    result = extract_fingerprint(
        apply_roi(photo, params.roi),
        period=params.period,
        min_quality=params.min_quality,
        flip=params.flip,
        crop=params.crop,
        debug=params.debug,
        options=params.options,
    )
    stem = evidence.label.rsplit(".", 1)[0]
    outputs, export_fields = _store_outputs(
        case, result, stem, job_id=job_id, params=params, nfiq2_command=nfiq2_command
    )
    measurements = {
        "ridge_period_px": result.period,
        "found_finger": result.found_finger,
        "output_scale": result.output_scale,
        "print_area": print_area(result, params.roi),
        "channel_used": result.channel_used,
        "specular_fraction": result.specular_fraction,
    }
    source: dict[str, Any] = {
        "sha256": evidence.sha256,
        "label": evidence.label,
        **_probe(data, photo),
        **({"source": evidence.source} if evidence.source else {}),
    }
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "job_id": job_id,
        "case_id": case.case_id,
        "case_reference": case.meta().case_reference,
        "created_utc": utc_now(),
        "ridge": environment(),
        "input": source,
        "parameters": params.to_json(),
        "submission": submission_record(submission, source.get("metadata")),
        "measurements": measurements,
        **export_fields,
        "limits_of_use": report_section(limits_of_use, {"measurements": measurements, **export_fields}),
        "outputs": [{"role": o.role, "label": o.label, "sha256": o.sha256, "size": o.size} for o in outputs],
        "custody_head": case.custody.head,
        "signer": {"key_id": signer.key_id, "public_key": b64(signer.public_key)},
        "disclaimer": DISCLAIMER,
    }
    _sign_and_close(case, job_id, report, signer)
    return JobOutcome(job_id, outputs, report)


def _store_outputs(
    case: OpenCase,
    result: ExtractionResult,
    stem: str,
    *,
    job_id: str,
    params: JobParams,
    nfiq2_command: Sequence[str] | None,
) -> tuple[list[StoredItem], dict[str, Any]]:
    """Store the print, debug images, comparison export and minutiae; return them and their report fields."""
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
    return outputs, export_fields


def _sign_and_close(case: OpenCase, job_id: str, report: dict[str, Any], signer: Signer) -> None:
    """Store the signed canonical report, close the job in the custody log and sign the new head."""
    canonical = bytes(rfc8785.dumps(report))
    case.put_report(job_id, canonical, signer.sign(canonical))
    case.entries.append(
        case.custody.append("report.sign", job_id=job_id, report_sha256=sha256_hex(canonical), key_id=signer.key_id)
    )
    case.entries.append(case.custody.append("job.end", job_id=job_id))
    case.entries.append(case.custody.sign_head(signer))
