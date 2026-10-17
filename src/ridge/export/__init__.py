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
    ExportResult,
    ScaleEstimate,
    ScaleMethod,
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
    "ExportResult",
    "ScaleEstimate",
    "ScaleMethod",
    "encode_png",
    "make_comparison_export",
    "mirror",
    "scale_from_ridge_period",
    "scale_from_ruler",
    "to_comparison",
    "to_ppi",
]
