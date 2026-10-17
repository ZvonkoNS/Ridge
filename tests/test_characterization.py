"""Golden characterization: the package reproduces the v0 implementation (commit 3441cf8).

On the platform and library versions the goldens were generated with, results must be
bit-identical. Elsewhere they must agree on at least 99.9% of pixels (PRD NFR-3), with the
same shape, ridge spacing (to 1e-6 relative) and finger detection.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from ridge import ExtractionError, extract_fingerprint
from tests.conftest import Golden
from tests.golden_cases import CASES, Case
from tests.synthetic import ImageU8

MIN_AGREEMENT = 0.999


def assert_matches(actual: ImageU8, expected: ImageU8, *, exact: bool, label: str) -> None:
    assert actual.shape == expected.shape, label
    assert actual.dtype == expected.dtype, label
    if exact:
        assert np.array_equal(actual, expected), f"{label}: not bit-identical to v0"
    else:
        agreement = float(np.mean(actual == expected))
        assert agreement >= MIN_AGREEMENT, f"{label}: only {agreement:.4%} of pixels agree with v0"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_matches_v0(case: Case, golden: Golden) -> None:
    expected = golden.meta["cases"][case.name]
    if expected["status"] == "error":
        with pytest.raises(ExtractionError) as excinfo:
            extract_fingerprint(case.photo(), **case.params)
        assert str(excinfo.value) == expected["error"]
        assert isinstance(excinfo.value, ValueError)  # v0 callers caught ValueError
        return

    result = extract_fingerprint(case.photo(), debug=case.debug, **case.params)
    assert result.found_finger == expected["found_finger"]
    assert result.period == pytest.approx(expected["period"], rel=0 if golden.exact else 1e-6)
    assert_matches(result.image, golden.arrays[f"{case.name}__image"], exact=golden.exact, label=case.name)
    assert set(np.unique(result.image).tolist()) <= {0, 255}

    if not case.debug:
        assert result.debug is None
        return
    assert result.debug is not None
    for step in ("normalized", "gabor", "quality"):
        actual = getattr(result.debug, step)
        assert_matches(actual, golden.arrays[f"{case.name}__debug_{step}"], exact=golden.exact, label=step)
    # v0 stored the region overlay as JPEG; compare after the same encoding.
    region = cv2.imdecode(cv2.imencode(".jpg", result.debug.region)[1], cv2.IMREAD_UNCHANGED)
    assert region is not None
    expected_region = golden.arrays[f"{case.name}__debug_region"]
    if golden.exact:
        assert np.array_equal(region, expected_region)
    else:
        assert region.shape == expected_region.shape
        assert float(np.mean(np.abs(region.astype(np.int16) - expected_region))) <= 1.0


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
