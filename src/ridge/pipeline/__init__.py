"""Pure extraction pipeline: NumPy arrays in, NumPy arrays out. No I/O, clock or randomness."""

from __future__ import annotations

from ridge.pipeline.extract import WORK_PERIOD, DebugImages, ExtractionResult, extract_fingerprint

__all__ = ["WORK_PERIOD", "DebugImages", "ExtractionResult", "extract_fingerprint"]
