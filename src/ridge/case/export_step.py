"""Comparison exports and indicative NFIQ 2 score inside a case job (PRD FR-30 to FR-34, FR-37).

Two exports with the same geometry (dark ridges, mirrored, 500 ppi) are stored: the binary one
from the print as an ``export`` artefact, and its grayscale twin as an ``export-gray`` artefact,
both recorded in the job report together with every transform, the scale method and its
uncertainty. A scale that would make the export impossible (e.g. a wrong ruler) does not fail
the job: the report says why no export was produced, so the examiner can rerun with a better
scale.

NFIQ 2 runs only when the lab has configured the NIST tool, on the grayscale export (the image
a feature extractor would take; the report names it). Its score is indicative only
(photo-derived image, outside ISO/IEC 29794-4 scope) and is labelled so in the report. The
temporary copy the tool needs lives in a private ``work`` folder inside the case and is
removed straight away.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import rfc8785

from ridge.case.case_model import StoredItem
from ridge.case.store import OpenCase
from ridge.errors import ExportError, ExtractionError, ParameterError
from ridge.export import (
    ASSUMED_RIDGE_PERIOD_MM,
    REFERENCE_OBJECTS,
    ReferenceKind,
    ScaleEstimate,
    encode_png,
    make_comparison_export,
    scale_from_reference,
    scale_from_ridge_period,
)
from ridge.export.validate import ppi_value
from ridge.minutiae import extract_minutiae, to_export_space
from ridge.pipeline import ExtractionResult
from ridge.quality.nfiq2 import Nfiq2, Nfiq2NotComputed, check_command

NFIQ2_LABEL = "indicative only: NFIQ 2 is defined for contact prints, this image is derived from a photo"
MINUTIAE_LABEL = "unvalidated automatic minutiae for examiner review; not used for any matching"
NFIQ2_PPI = 500.0
GRAY_ROLE = "export-gray"  # stored role of the grayscale comparison export (FR-37)
# Recorded when an export had to be enlarged to reach its resolution (FR-32): more pixels, no more detail.
UPSAMPLING_TOLERANCE = 1.05  # rounding the output size to whole pixels can give factors just above 1
RESOLUTION_NOTE = (
    "The export was enlarged {factor:.2f} times to reach {ppi:g} ppi: the photo holds fewer pixels per millimetre "
    "than that, so the export carries no detail beyond the photo's own resolution."
)
# Recorded with every export scaled without a reference object (FR-31; product owner, 2026-10-24).
SCALE_NOTICE = (
    "No scale reference was given: the export scale is estimated from the ridge spacing and an assumed "
    "ridge distance (+-15 %). If possible, photograph the finger again with a ruler or an ISO/IEC 7810 ID-1 "
    "card (bank-card size) in the plane of the finger pad and mark two points on it, or mark one that is "
    "already in the photo. Otherwise proceed with this estimate and state it wherever the export is used."
)


@dataclass(frozen=True)
class ExportOptions:
    """How the comparison export is made (recorded in the job report)."""

    enabled: bool = True
    mirror: bool = True
    target_ppi: float = 500.0
    ruler: tuple[float, float, float, float, float] | None = None  # x1, y1, x2, y2 (photo px), distance mm
    reference: ReferenceKind = "ruler"  # what the two points lie on: a ruler or an ID-1 card edge (FR-31 a)

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form (lists, not tuples)."""
        data = asdict(self)
        data["ruler"] = None if self.ruler is None else list(self.ruler)
        return data


def validate_job_settings(options: ExportOptions, nfiq2_command: Sequence[str] | None) -> None:
    """Refuse invalid export or NFIQ 2 settings before a job starts (raises ParameterError)."""
    if options.enabled:
        ppi_value(options.target_ppi, "target_ppi")
        if options.reference not in REFERENCE_OBJECTS:
            raise ParameterError(f"the scale reference must be one of {', '.join(REFERENCE_OBJECTS)}")
        if options.ruler is not None:
            if len(options.ruler) != 5:
                raise ParameterError("ruler needs x1, y1, x2, y2 and the distance in mm")
            x1, y1, x2, y2, mm = options.ruler
            scale_from_reference((x1, y1), (x2, y2), mm, options.reference)
        elif options.reference != "ruler":
            raise ParameterError(f"the scale reference {options.reference} needs its two points (ruler)")
    if nfiq2_command is not None:
        check_command(nfiq2_command)


def photo_scale(result: ExtractionResult, options: ExportOptions) -> ScaleEstimate:
    """Reference-object calibration when points are given (FR-31 a), else the ridge-period assumption (FR-31 b)."""
    if options.ruler is not None:
        x1, y1, x2, y2, mm = options.ruler
        return scale_from_reference((x1, y1), (x2, y2), mm, options.reference)
    return scale_from_ridge_period(result.period)


def export_and_score(
    case: OpenCase,
    result: ExtractionResult,
    *,
    stem: str,
    job_id: str,
    options: ExportOptions,
    nfiq2_command: Sequence[str] | None,
) -> tuple[list[StoredItem], dict[str, Any]]:
    """Store both comparison exports and return (artefacts, report fields ``export`` and ``quality``).

    The binary export is the ``export`` artefact the report describes; its grayscale twin is the
    ``export-gray`` artefact named under ``export.grayscale``. NFIQ 2 scores the grayscale one.
    """
    if not options.enabled:
        return [], {"export": None, "quality": None}
    scale = photo_scale(result, options)
    try:
        binary = make_comparison_export(result, scale, mirror_image=options.mirror, target_ppi=options.target_ppi)
        gray = make_comparison_export(
            result, scale, mirror_image=options.mirror, target_ppi=options.target_ppi, tone="grayscale"
        )
    except ExportError as exc:
        return [], {"export": {"produced": False, "reason": str(exc)}, "quality": None}
    png, gray_png = encode_png(binary.image, binary.ppi), encode_png(gray.image, gray.ppi)
    item = case.store_artefact(png, role="export", label=f"{stem}_comparison_{binary.ppi:g}ppi.png", job_id=job_id)
    gray_label = f"{stem}_comparison_gray_{gray.ppi:g}ppi.png"
    gray_item = case.store_artefact(gray_png, role=GRAY_ROLE, label=gray_label, job_id=job_id)
    export_info = {
        "produced": True,
        "sha256": item.sha256,
        "ppi": binary.ppi,
        "factor": binary.factor,
        "transforms": list(binary.transforms),
        "scale": _scale_info(scale),
        "grayscale": {"sha256": gray_item.sha256, "transforms": list(gray.transforms)},
    }
    # The pipeline already enlarges a low-resolution photo's print (output_scale > 1), so the export's
    # pixels per photo pixel are the two factors together; that is what says whether detail was invented.
    enlargement = binary.factor * result.output_scale
    export_info["pixels_per_photo_pixel"] = enlargement
    if enlargement > UPSAMPLING_TOLERANCE:
        export_info["resolution_note"] = RESOLUTION_NOTE.format(factor=enlargement, ppi=binary.ppi)
    quality = {"nfiq2": nfiq2_score(case, gray_png, gray.ppi, nfiq2_command, image=GRAY_ROLE)}
    return [item, gray_item], {"export": export_info, "quality": quality}


def _scale_info(scale: ScaleEstimate) -> dict[str, Any]:
    info: dict[str, Any] = {
        "method": scale.method,
        "px_per_mm": scale.px_per_mm,
        "uncertainty_pct": scale.uncertainty_pct,
    }
    if scale.reference is not None:
        info["reference"] = scale.reference
    if scale.method == "ridge-period":
        info["assumed_ridge_period_mm"] = ASSUMED_RIDGE_PERIOD_MM
        info["notice"] = SCALE_NOTICE
    return info


def nfiq2_score(
    case: OpenCase, png: bytes, ppi: float, command: Sequence[str] | None, *, image: str = "export"
) -> dict[str, Any]:
    """NFIQ 2 result for the report: score with label, or why it was not computed; `image` names the scored role."""
    if command is None:
        return {"computed": False, "reason": "NFIQ 2 is not configured", "image": image}
    if ppi != NFIQ2_PPI:
        reason = f"NFIQ 2 is defined for {NFIQ2_PPI:g} ppi; this export is {ppi:g} ppi"
        return {"computed": False, "reason": reason, "image": image}
    work = case.dir / "work"
    work.mkdir(mode=0o700, exist_ok=True)
    try:
        outcome = Nfiq2(command, work_dir=work).assess(png)
    finally:
        with contextlib.suppress(OSError):
            work.rmdir()  # Nfiq2 removes its own private folder; leave nothing behind
    if isinstance(outcome, Nfiq2NotComputed):
        return {"computed": False, "reason": outcome.reason, "image": image}
    return {"computed": True, "score": outcome.score, "version": outcome.version, "label": NFIQ2_LABEL, "image": image}


def minutiae_step(
    case: OpenCase,
    result: ExtractionResult,
    *,
    stem: str,
    job_id: str,
    export: dict[str, Any] | None,
    mirrored: bool,
) -> tuple[list[StoredItem], dict[str, Any]]:
    """Store minutiae (print space, and export space when an export exists) and summarise them."""
    try:
        found = extract_minutiae(result.image, result.period * result.output_scale)
    except ExtractionError as exc:  # not a job failure: the print and export stand on their own
        return [], {"minutiae": {"produced": False, "reason": str(exc), "label": MINUTIAE_LABEL}}
    doc = found.to_json()
    if export and export.get("produced"):
        doc["export_space"] = to_export_space(found, factor=export["factor"], mirrored=mirrored).to_json()
    item = case.store_artefact(bytes(rfc8785.dumps(doc)), role="minutiae", label=f"{stem}_minutiae.json", job_id=job_id)
    kinds = [m.kind for m in found.minutiae]
    summary = {
        "produced": True,
        "sha256": item.sha256,
        "count": len(kinds),
        "endings": kinds.count("ending"),
        "bifurcations": kinds.count("bifurcation"),
        "label": MINUTIAE_LABEL,
    }
    return [item], {"minutiae": summary}
