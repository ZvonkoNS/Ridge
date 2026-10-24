"""Pure extraction pipeline: NumPy arrays in, NumPy arrays out. No I/O, clock or randomness."""

from __future__ import annotations

from ridge.pipeline.enhance import WORK_PERIOD
from ridge.pipeline.extract import DebugImages, ExtractionResult, extract_fingerprint
from ridge.pipeline.options import CHANNELS, Channel, MethodOptions

__all__ = [
    "CHANNELS",
    "WORK_PERIOD",
    "Channel",
    "DebugImages",
    "ExtractionResult",
    "MethodOptions",
    "extract_fingerprint",
]
