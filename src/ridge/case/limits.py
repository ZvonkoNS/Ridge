"""Limits of use from the laboratory's method validation, checked on every job (PRD §12 item 8).

The Forensic Quality Manager places ``limits-of-use.json`` in the case store. Ridge never
invents limits and ships none: without the file, every report says ``configured: false``.
With it, each job compares its own measurements with the limits and records any deviation as
a warning in the signed report, together with the file's SHA-256 and its stated source (the
validation report). A job outside the limits is not refused: the examiner decides, informed.
A malformed limits file stops jobs (fail closed, SEC-9) until it is corrected.
"""

from __future__ import annotations

import json
import math
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ridge.case.crypto import sha256_hex
from ridge.errors import ParameterError
from ridge.image_io import read_bounded

FILE = "limits-of-use.json"
SCHEMA = "ridge.limits-of-use/1"
MAX_BYTES = 64 * 1024
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_NUMBERS = ("min_ridge_period_px", "max_ridge_period_px", "max_scale_uncertainty_pct", "min_nfiq2")
_FLAGS = ("require_ruler", "require_finger_found")
_KEYS = {"schema", "source", "architectures", *_NUMBERS, *_FLAGS}


@dataclass(frozen=True)
class LimitsOfUse:
    """Limits stated by the laboratory's validation report; every limit is optional."""

    source: str
    sha256: str
    architectures: tuple[str, ...] = ()
    min_ridge_period_px: float | None = None
    max_ridge_period_px: float | None = None
    max_scale_uncertainty_pct: float | None = None
    min_nfiq2: float | None = None
    require_ruler: bool = False
    require_finger_found: bool = False

    def to_json(self) -> dict[str, Any]:
        """Return the limits as recorded in a report."""
        limits = {k: getattr(self, k) for k in (*_NUMBERS, *_FLAGS) if getattr(self, k) not in (None, False)}
        if self.architectures:
            limits["architectures"] = list(self.architectures)
        return limits


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200 or _CONTROL.search(value):
        raise ParameterError(f"limits of use: {what} must be 1-200 printable characters")
    return value.strip()


def _number(value: object, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ParameterError(f"limits of use: {what} must be a non-negative number")
    return float(value)


def parse_limits(data: bytes) -> LimitsOfUse:
    """Validate a limits file strictly: known keys only, typed values, consistent ranges."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ParameterError("limits of use: not a UTF-8 JSON document") from None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ParameterError(f"limits of use: the schema must be {SCHEMA!r}")
    unknown = set(doc) - _KEYS
    if unknown:
        raise ParameterError(f"limits of use: unknown field(s) {', '.join(sorted(unknown))}")
    numbers = {k: _number(doc.get(k), k) for k in _NUMBERS}
    flags = {k: doc.get(k, False) for k in _FLAGS}
    if not all(isinstance(v, bool) for v in flags.values()):
        raise ParameterError("limits of use: require_ruler and require_finger_found must be true or false")
    archs = doc.get("architectures", [])
    if not isinstance(archs, list) or len(archs) > 16:
        raise ParameterError("limits of use: architectures must be a list of at most 16 names")
    low, high = numbers["min_ridge_period_px"], numbers["max_ridge_period_px"]
    if low is not None and high is not None and low > high:
        raise ParameterError("limits of use: min_ridge_period_px is above max_ridge_period_px")
    return LimitsOfUse(
        source=_text(doc.get("source"), "source"),
        sha256=sha256_hex(data),
        architectures=tuple(_text(a, "an architecture name") for a in archs),
        min_ridge_period_px=low,
        max_ridge_period_px=high,
        max_scale_uncertainty_pct=numbers["max_scale_uncertainty_pct"],
        min_nfiq2=numbers["min_nfiq2"],
        require_ruler=flags["require_ruler"],
        require_finger_found=flags["require_finger_found"],
    )


def load_limits(store: Path) -> LimitsOfUse | None:
    """Return the store's limits of use, or None when the laboratory has not configured any."""
    path = store / FILE
    if not path.exists():
        return None
    return parse_limits(read_bounded(path, MAX_BYTES))


def deviations(limits: LimitsOfUse, fields: dict[str, Any], machine: str | None = None) -> list[str]:
    """Where a job's report fields fall outside the limits, in plain words (empty when within)."""
    found: list[str] = []
    machine = machine or platform.machine()
    if limits.architectures and machine not in limits.architectures:
        found.append(
            f"this workstation's CPU architecture ({machine}) is not among those the limits cover "
            f"({', '.join(limits.architectures)})"
        )
    measurements = fields.get("measurements") or {}
    period = measurements.get("ridge_period_px")
    if isinstance(period, int | float):
        if limits.min_ridge_period_px is not None and period < limits.min_ridge_period_px:
            found.append(f"ridge period {period:.2f} px is below the minimum of {limits.min_ridge_period_px:g} px")
        if limits.max_ridge_period_px is not None and period > limits.max_ridge_period_px:
            found.append(f"ridge period {period:.2f} px is above the maximum of {limits.max_ridge_period_px:g} px")
    if limits.require_finger_found and not measurements.get("found_finger"):
        found.append("the finger was not located (the whole frame was used); the limits require a located finger")
    found.extend(_export_deviations(limits, fields.get("export")))
    found.extend(_quality_deviations(limits, fields.get("quality")))
    return found


def _export_deviations(limits: LimitsOfUse, export: dict[str, Any] | None) -> list[str]:
    if not (limits.require_ruler or limits.max_scale_uncertainty_pct is not None):
        return []
    if not export or not export.get("produced"):
        return ["no comparison export was produced, so its scale could not be checked against the limits"]
    scale = export.get("scale") or {}
    found = []
    if limits.require_ruler and scale.get("method") != "ruler":
        found.append(f"the export scale comes from {scale.get('method')}; the limits require a ruler in the photo")
    uncertainty = scale.get("uncertainty_pct")
    maximum = limits.max_scale_uncertainty_pct
    if maximum is not None and isinstance(uncertainty, int | float) and uncertainty > maximum:
        found.append(f"the export scale uncertainty (±{uncertainty:g} %) exceeds the maximum of ±{maximum:g} %")
    return found


def _quality_deviations(limits: LimitsOfUse, quality: dict[str, Any] | None) -> list[str]:
    if limits.min_nfiq2 is None:
        return []
    nfiq2 = (quality or {}).get("nfiq2") or {}
    if not nfiq2.get("computed"):
        return [f"no NFIQ 2 score was computed; the limits set a minimum of {limits.min_nfiq2:g}"]
    score = nfiq2.get("score")
    if isinstance(score, int | float) and score < limits.min_nfiq2:
        return [f"the NFIQ 2 score {score:g} is below the minimum of {limits.min_nfiq2:g}"]
    return []


def report_section(limits: LimitsOfUse | None, fields: dict[str, Any]) -> dict[str, Any]:
    """Build the ``limits_of_use`` section of a job report."""
    if limits is None:
        return {"configured": False}
    warnings = deviations(limits, fields)
    return {
        "configured": True,
        "source": limits.source,
        "sha256": limits.sha256,
        "limits": limits.to_json(),
        "within": not warnings,
        "warnings": warnings,
    }


def render_lines(section: dict[str, Any] | None) -> list[str]:
    """Render a report's ``limits_of_use`` section as text lines (older reports have none)."""
    if not section:
        return []
    if not section.get("configured"):
        return ["Limits        none configured for this store"]
    head = f"Limits        {section.get('source')} (sha256 {str(section.get('sha256'))[:16]}...)"
    if section.get("within"):
        return [head, "              within the limits of use"]
    return [
        head,
        "              outside the limits of use:",
        *(f"              - {w}" for w in section.get("warnings") or []),
    ]
