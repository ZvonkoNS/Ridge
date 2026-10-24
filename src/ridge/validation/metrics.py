"""Verification and identification metrics for the method validation study (PRD §12, ISO/IEC 19795-1).

Input is comparison scores from an external matcher (e.g. SourceAFIS or NIST NBIS) run by the
lab on its consented validation set, outside the repository: genuine comparisons (same finger)
and impostor comparisons (different fingers), higher score = more similar; and, for 1:N
searches as an AFIS runs them, the rank at which each probe's mate was returned.

* FMR(t)  = share of impostor scores >= t; FNMR(t) = share of genuine scores < t.
* FNMR at a target FMR uses the lowest threshold whose FMR does not exceed the target.
* Rank-k hit rate = share of probes whose mate was returned at rank k or better; the CMC curve
  is that share for every rank up to a maximum (ISO/IEC 19795-1 identification metrics).
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
MAX_RANK = 1000  # candidate lists longer than this are not a search result an examiner reviews


def wilson_interval(count: int, trials: int) -> tuple[float, float]:
    """Wilson score interval (95 %) for `count` successes in `trials`, exact at the extremes."""
    n, p = trials, count / trials
    centre = (p + Z95**2 / (2 * n)) / (1 + Z95**2 / n)
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n * n)) / (1 + Z95**2 / n)
    low = 0.0 if count == 0 else max(0.0, centre - half)
    high = 1.0 if count == n else min(1.0, centre + half)
    return low, high


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
        return wilson_interval(self.errors, self.trials)

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


# ------------------------------------------------------------------ identification (1:N) metrics


@dataclass(frozen=True)
class HitRate:
    """A rank-k hit rate: probes whose mate was returned at rank k or better, out of all probes."""

    hits: int
    trials: int

    @property
    def value(self) -> float:
        """Return hits / trials."""
        return self.hits / self.trials

    def wilson(self) -> tuple[float, float]:
        """Wilson score interval (95 %)."""
        return wilson_interval(self.hits, self.trials)

    def to_json(self) -> dict[str, Any]:
        """JSON form."""
        low, high = self.wilson()
        return {"value": self.value, "hits": self.hits, "trials": self.trials, "ci95": [low, high]}


def _ranks(ranks: list[int | None]) -> list[int | None]:
    if not ranks:
        raise ParameterError("rank lists must not be empty")
    for rank in ranks:
        value: object = rank  # callers that bypass the type checker still get a clear refusal
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_RANK):
            raise ParameterError(
                f"a rank is a whole number from 1 to {MAX_RANK}, or None when the mate was not returned"
            )
    return ranks


def _rank_k(k: object) -> int:
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= MAX_RANK:
        raise ParameterError(f"k must be a whole number from 1 to {MAX_RANK}")
    return k


def hit_rate(ranks: list[int | None], k: int) -> HitRate:
    """Share of probes whose mate was returned at rank `k` or better (None: the mate was not returned)."""
    checked, top = _ranks(ranks), _rank_k(k)
    return HitRate(sum(1 for r in checked if r is not None and r <= top), len(checked))


def cmc_curve(ranks: list[int | None], max_rank: int) -> list[tuple[int, float]]:
    """(rank, cumulative hit rate) for every rank from 1 to `max_rank`: the CMC curve."""
    checked, top = _ranks(ranks), _rank_k(max_rank)
    returned = sorted(r for r in checked if r is not None)
    n = len(checked)
    return [(k, int(np.searchsorted(returned, k, side="right")) / n) for k in range(1, top + 1)]


def not_returned(ranks: list[int | None]) -> int:
    """Probes whose mate was not in the candidate list at all."""
    return sum(1 for r in _ranks(ranks) if r is None)
