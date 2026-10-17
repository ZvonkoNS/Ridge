"""Verification-performance metrics for the method validation study (PRD §12, ISO/IEC 19795-1).

Input is comparison scores from an external matcher (e.g. SourceAFIS or NIST NBIS) run by the
lab on its consented validation set, outside the repository: genuine comparisons (same finger)
and impostor comparisons (different fingers), higher score = more similar.

* FMR(t)  = share of impostor scores >= t; FNMR(t) = share of genuine scores < t.
* FNMR at a target FMR uses the lowest threshold whose FMR does not exceed the target.
* Confidence intervals are Wilson score intervals (95 %); they assume independent
  comparisons, which repeated use of the same finger violates, so treat them as optimistic.
* "Rule of 30" (ISO/IEC 19795-1): an error rate is only supported when at least 30 errors
  could be observed at that rate, i.e. n >= 30 / rate comparisons.

The numbers describe Ridge exports compared by a matcher. They are evidence for the
validation report, not a property of any single case.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ridge.errors import ParameterError

Z95 = 1.959963984540054


@dataclass(frozen=True)
class Rate:
    """An error rate with its count, sample size and Wilson 95 % interval."""

    errors: int
    trials: int

    @property
    def value(self) -> float:
        """Return errors / trials."""
        return self.errors / self.trials

    def wilson(self) -> tuple[float, float]:
        """Wilson score interval (95 %)."""
        n, p = self.trials, self.value
        centre = (p + Z95**2 / (2 * n)) / (1 + Z95**2 / n)
        half = Z95 * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n * n)) / (1 + Z95**2 / n)
        low = 0.0 if self.errors == 0 else max(0.0, centre - half)  # exact bounds at the extremes
        high = 1.0 if self.errors == n else min(1.0, centre + half)
        return low, high

    def to_json(self) -> dict[str, Any]:
        """JSON form."""
        low, high = self.wilson()
        return {"value": self.value, "errors": self.errors, "trials": self.trials, "ci95": [low, high]}


def _scores(values: NDArray[np.float64] | list[float], what: str) -> NDArray[np.float64]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or arr.size == 0:
        raise ParameterError(f"{what} scores must be a non-empty list")
    if not np.isfinite(arr).all():
        raise ParameterError(f"{what} scores must be finite numbers")
    return arr


@dataclass(frozen=True)
class OperatingPoint:
    """FNMR and achieved FMR at the threshold chosen for a target FMR."""

    target_fmr: float
    threshold: float
    fmr: Rate
    fnmr: Rate
    supported: bool  # rule of 30: enough impostor comparisons to claim this FMR

    def to_json(self) -> dict[str, Any]:
        """JSON form."""
        return {
            "target_fmr": self.target_fmr,
            "threshold": self.threshold,
            "fmr": self.fmr.to_json(),
            "fnmr": self.fnmr.to_json(),
            "supported_by_rule_of_30": self.supported,
        }


def _error_counts(
    gen: NDArray[np.float64], imp: NDArray[np.float64], thresholds: NDArray[np.float64]
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """Count false matches (impostor >= t) and false non-matches (genuine < t) per threshold, O(n log n)."""
    g, i = np.sort(gen), np.sort(imp)
    false_matches = i.size - np.searchsorted(i, thresholds, side="left")
    false_non_matches = np.searchsorted(g, thresholds, side="left")
    return false_matches, false_non_matches


def operating_point(genuine: list[float], impostor: list[float], target_fmr: float) -> OperatingPoint:
    """FNMR at the lowest threshold whose FMR does not exceed `target_fmr`."""
    if not 0.0 < target_fmr < 1.0:
        raise ParameterError("target_fmr must be between 0 and 1")
    gen, imp = _scores(genuine, "genuine"), _scores(impostor, "impostor")
    candidates = np.unique(np.concatenate([gen, imp, [np.nextafter(imp.max(), np.inf)]]))  # ascending
    false_matches, false_non_matches = _error_counts(gen, imp, candidates)
    first = int(np.argmax(false_matches / imp.size <= target_fmr))  # the top candidate always qualifies
    return OperatingPoint(
        target_fmr,
        float(candidates[first]),
        Rate(int(false_matches[first]), imp.size),
        Rate(int(false_non_matches[first]), gen.size),
        imp.size >= 30 / target_fmr,
    )


def det_curve(genuine: list[float], impostor: list[float], max_points: int = 200) -> list[tuple[float, float, float]]:
    """(threshold, FMR, FNMR) points over all score thresholds, thinned to at most `max_points`."""
    gen, imp = _scores(genuine, "genuine"), _scores(impostor, "impostor")
    thresholds = np.unique(np.concatenate([gen, imp]))
    if thresholds.size > max_points:
        thresholds = thresholds[np.linspace(0, thresholds.size - 1, max_points).round().astype(int)]
    false_matches, false_non_matches = _error_counts(gen, imp, thresholds)
    return [
        (float(t), int(fm) / imp.size, int(fnm) / gen.size)
        for t, fm, fnm in zip(thresholds, false_matches, false_non_matches, strict=True)
    ]


def equal_error_rate(genuine: list[float], impostor: list[float]) -> tuple[float, float]:
    """(EER estimate, threshold): the threshold where FMR and FNMR are closest (their mean)."""
    gen, imp = _scores(genuine, "genuine"), _scores(impostor, "impostor")
    thresholds = np.unique(np.concatenate([gen, imp]))
    false_matches, false_non_matches = _error_counts(gen, imp, thresholds)
    fmr, fnmr = false_matches / imp.size, false_non_matches / gen.size
    best = int(np.argmin(np.abs(fmr - fnmr)))
    return float((fmr[best] + fnmr[best]) / 2), float(thresholds[best])


def failure_to_extract(attempts: int, failures: int) -> Rate:
    """Share of validation photos for which Ridge produced no usable export (FTX)."""
    if attempts <= 0 or not 0 <= failures <= attempts:
        raise ParameterError("need attempts > 0 and 0 <= failures <= attempts")
    return Rate(failures, attempts)
