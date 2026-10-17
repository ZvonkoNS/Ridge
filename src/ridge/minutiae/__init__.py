"""Minutiae extraction (milestone M3): ridge endings and bifurcations for examiner comparison."""

from __future__ import annotations

from ridge.minutiae.extract import Minutia, MinutiaeResult, extract_minutiae, to_export_space
from ridge.minutiae.skeleton import crossing_number, thin

__all__ = ["Minutia", "MinutiaeResult", "crossing_number", "extract_minutiae", "thin", "to_export_space"]
