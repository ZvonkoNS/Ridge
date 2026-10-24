"""Comparison exports (M2): dark ridges on light, mirrored, scaled to 500 ppi, lossless PNG.

Pure functions on arrays and bytes; writing files stays with ``ridge.image_io.publish``.
Exports are processed images for examiner comparison, never an identification.
"""

from __future__ import annotations

from ridge.export.png import encode_png
from ridge.export.transforms import (
    ASSUMED_RIDGE_PERIOD_MM,
    DEFAULT_PPI,
    MAX_EXPORT_PIXELS,
    RIDGE_PERIOD_UNCERTAINTY_PCT,
    TONE_GRAYSCALE,
    TONES,
    ExportResult,
    ScaleEstimate,
    ScaleMethod,
    Tone,
    make_comparison_export,
    mirror,
    scale_from_ridge_period,
    scale_from_ruler,
    to_comparison,
    to_ppi,
)

__all__ = [
    "ASSUMED_RIDGE_PERIOD_MM",
    "DEFAULT_PPI",
    "MAX_EXPORT_PIXELS",
    "RIDGE_PERIOD_UNCERTAINTY_PCT",
    "TONES",
    "TONE_GRAYSCALE",
    "ExportResult",
    "ScaleEstimate",
    "ScaleMethod",
    "Tone",
    "encode_png",
    "make_comparison_export",
    "mirror",
    "scale_from_ridge_period",
    "scale_from_ruler",
    "to_comparison",
    "to_ppi",
]
