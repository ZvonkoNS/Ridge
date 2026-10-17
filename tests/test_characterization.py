"""Characterization: the package reproduces the v0 implementation (commit 3441cf8).

Two independent checks (PRD NFR-3):

* ``test_bit_identical_to_live_v0`` runs v0 from git history on this machine and demands
  bit-identical results on every platform. This proves behaviour preservation.
* ``test_matches_stored_golden`` compares against the stored goldens for this CPU
  architecture. On the reference machine results must be bit-identical; on other machines of
  the same architecture (different CPU features) at least 99.9% of output pixels must agree,
  the ridge spacing must match to 1e-6 relative and debug images must agree to within one grey
  level on average. This detects drift from library or toolchain changes.

Results are *not* compared across architectures: x86-64 and arm64 legitimately differ.
"""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np
import pytest

from ridge import ExtractionError, extract_fingerprint
from tests.conftest import Golden
from tests.golden_cases import CASES, Case
from tests.reference import DEBUG_STEPS
from tests.synthetic import ImageU8

MIN_AGREEMENT = 0.999
MAX_DEBUG_MEAN_ABS_DIFF = 1.0


def assert_output_matches(actual: ImageU8, expected: ImageU8, *, exact: bool, label: str) -> None:
    assert actual.shape == expected.shape, label
    assert actual.dtype == expected.dtype, label
    if exact:
        assert np.array_equal(actual, expected), f"{label}: not bit-identical"
    else:
        agreement = float(np.mean(actual == expected))
        assert agreement >= MIN_AGREEMENT, f"{label}: only {agreement:.4%} of pixels agree"


def assert_debug_matches(actual: ImageU8, expected: ImageU8, *, exact: bool, label: str) -> None:
    """Debug images are quantised float maps: compare grey levels, not exact pixel equality."""
    assert actual.shape == expected.shape, label
    if exact:
        assert np.array_equal(actual, expected), f"{label}: not bit-identical"
    else:
        diff = float(np.mean(np.abs(actual.astype(np.int16) - expected.astype(np.int16))))
        assert diff <= MAX_DEBUG_MEAN_ABS_DIFF, f"{label}: mean difference {diff:.2f} grey levels"


def check_case(case: Case, expected: Golden) -> None:
    entry = expected.cases[case.name]
    if entry["status"] == "error":
        with pytest.raises(ExtractionError) as excinfo:
            extract_fingerprint(case.photo(), **case.params)
        assert str(excinfo.value) == entry["error"]
        assert isinstance(excinfo.value, ValueError)  # v0 callers caught ValueError
        return

    result = extract_fingerprint(case.photo(), debug=case.debug, **case.params)
    label = f"{case.name} vs {expected.source}"
    assert result.found_finger == entry["found_finger"], label
    assert result.period == pytest.approx(entry["period"], rel=0 if expected.exact else 1e-6), label
    assert_output_matches(result.image, expected.arrays[f"{case.name}__image"], exact=expected.exact, label=label)
    assert set(np.unique(result.image).tolist()) <= {0, 255}

    if not case.debug:
        assert result.debug is None
        return
    assert result.debug is not None
    for step in DEBUG_STEPS:
        expected_step = expected.arrays[f"{case.name}__debug_{step}"]
        assert_debug_matches(getattr(result.debug, step), expected_step, exact=expected.exact, label=f"{label} {step}")
    # v0 stored the region overlay as JPEG; compare after the same encoding.
    region = cv2.imdecode(cv2.imencode(".jpg", result.debug.region)[1], cv2.IMREAD_UNCHANGED)
    assert region is not None
    region = cast(ImageU8, region)
    expected_region = expected.arrays[f"{case.name}__debug_region"]
    assert_debug_matches(region, expected_region, exact=expected.exact, label=f"{label} region")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_bit_identical_to_live_v0(case: Case, live_v0: Golden) -> None:
    check_case(case, live_v0)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_matches_stored_golden(case: Case, golden: Golden) -> None:
    check_case(case, golden)


def test_repeat_runs_are_bit_identical() -> None:
    """Reproducibility (PRD G-3): the same input in the same process gives the same output."""
    photo = CASES[0].photo()
    first = extract_fingerprint(photo)
    second = extract_fingerprint(photo.copy())
    assert np.array_equal(first.image, second.image)
    assert first.period == second.period


def test_input_is_not_modified() -> None:
    """Evidence integrity: extraction never writes into the caller's array."""
    photo = CASES[0].photo()
    before = photo.copy()
    extract_fingerprint(photo, debug=True)
    assert np.array_equal(photo, before)
