"""Comparison export and indicative NFIQ 2 score inside a case job (PRD FR-30 to FR-34).

The export (dark ridges, mirrored, 500 ppi) is stored as an ``export`` artefact and recorded
in the job report together with every transform, the scale method and its uncertainty. A
scale that would make the export impossible (e.g. a wrong ruler) does not fail the job: the
report says why no export was produced, so the examiner can rerun with a better scale.

NFIQ 2 runs only when the lab has configured the NIST tool. Its score is indicative only
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

from ridge.case.store import OpenCase, StoredItem
from ridge.errors import ExportError
from ridge.export import (
    ASSUMED_RIDGE_PERIOD_MM,
    ScaleEstimate,
    encode_png,
    make_comparison_export,
    scale_from_ridge_period,
    scale_from_ruler,
)
from ridge.minutiae import extract_minutiae, to_export_space
from ridge.pipeline import ExtractionResult
from ridge.quality.nfiq2 import Nfiq2, Nfiq2NotComputed

NFIQ2_LABEL = "indicative only: NFIQ 2 is defined for contact prints, this image is derived from a photo"
MINUTIAE_LABEL = "unvalidated automatic minutiae for examiner review; not used for any matching"


@dataclass(frozen=True)
class ExportOptions:
    """How the comparison export is made (recorded in the job report)."""

    enabled: bool = True
    mirror: bool = True
    target_ppi: float = 500.0
    ruler: tuple[float, float, float, float, float] | None = None  # x1, y1, x2, y2 (photo px), distance mm

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form (lists, not tuples)."""
        data = asdict(self)
        data["ruler"] = None if self.ruler is None else list(self.ruler)
        return data


def photo_scale(result: ExtractionResult, options: ExportOptions) -> ScaleEstimate:
    """Ruler calibration when given (FR-31 a), else the ridge-period assumption (FR-31 b)."""
    if options.ruler is not None:
        x1, y1, x2, y2, mm = options.ruler
        return scale_from_ruler((x1, y1), (x2, y2), mm)
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
    """Store the comparison export and return (artefacts, report fields ``export`` and ``quality``)."""
    if not options.enabled:
        return [], {"export": None, "quality": None}
    scale = photo_scale(result, options)
    try:
        exported = make_comparison_export(result, scale, mirror_image=options.mirror, target_ppi=options.target_ppi)
    except ExportError as exc:
        return [], {"export": {"produced": False, "reason": str(exc)}, "quality": None}
    png = encode_png(exported.image, exported.ppi)
    label = f"{stem}_comparison_{exported.ppi:g}ppi.png"
    item = case.store_artefact(png, role="export", label=label, job_id=job_id)
    scale_info: dict[str, Any] = {
        "method": scale.method,
        "px_per_mm": scale.px_per_mm,
        "uncertainty_pct": scale.uncertainty_pct,
    }
    if scale.method == "ridge-period":
        scale_info["assumed_ridge_period_mm"] = ASSUMED_RIDGE_PERIOD_MM
    export_info = {
        "produced": True,
        "sha256": item.sha256,
        "ppi": exported.ppi,
        "factor": exported.factor,
        "transforms": list(exported.transforms),
        "scale": scale_info,
    }
    return [item], {"export": export_info, "quality": {"nfiq2": nfiq2_score(case, png, nfiq2_command)}}


def nfiq2_score(case: OpenCase, png: bytes, command: Sequence[str] | None) -> dict[str, Any]:
    """NFIQ 2 result for the report: score with label, or why it was not computed."""
    if command is None:
        return {"computed": False, "reason": "NFIQ 2 is not configured"}
    work = case.dir / "work"
    work.mkdir(mode=0o700, exist_ok=True)
    try:
        outcome = Nfiq2(command, work_dir=work).assess(png)
    finally:
        with contextlib.suppress(OSError):
            work.rmdir()  # Nfiq2 removes its own private folder; leave nothing behind
    if isinstance(outcome, Nfiq2NotComputed):
        return {"computed": False, "reason": outcome.reason}
    return {"computed": True, "score": outcome.score, "version": outcome.version, "label": NFIQ2_LABEL}


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
    found = extract_minutiae(result.image, result.period * result.output_scale)
    doc = found.to_json()
    if export and export.get("produced"):
        doc["export_space"] = to_export_space(found, factor=export["factor"], mirrored=mirrored).to_json()
    item = case.store_artefact(bytes(rfc8785.dumps(doc)), role="minutiae", label=f"{stem}_minutiae.json", job_id=job_id)
    kinds = [m.kind for m in found.minutiae]
    summary = {
        "sha256": item.sha256,
        "count": len(kinds),
        "endings": kinds.count("ending"),
        "bifurcations": kinds.count("bifurcation"),
        "label": MINUTIAE_LABEL,
    }
    return [item], {"minutiae": summary}
