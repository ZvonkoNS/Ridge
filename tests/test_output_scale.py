"""ExtractionResult.output_scale: output pixels per photo pixel, the input to 500 ppi export scaling.

Runs on the synthetic golden cases; the output pixels themselves are covered by
tests/test_characterization.py and are unchanged.
"""

from __future__ import annotations

import numpy as np

from ridge import ExtractionResult, extract_fingerprint
from ridge.pipeline import WORK_PERIOD
from tests.golden_cases import CASES_BY_NAME


def test_output_scale_when_cropping() -> None:
    result = extract_fingerprint(CASES_BY_NAME["whorl_default"].photo())
    assert result.output_scale == max(1.0, WORK_PERIOD / result.period)
    assert result.output_scale > 1.0  # ridges ~8.8 px apart: the output is finer than the photo
    assert type(result.output_scale) is float


def test_output_scale_is_one_for_coarse_ridges() -> None:
    case = CASES_BY_NAME["arch_large_period"]
    result = extract_fingerprint(case.photo(), **case.params)
    assert result.period > WORK_PERIOD
    assert result.output_scale == max(1.0, WORK_PERIOD / result.period) == 1.0


def test_output_scale_without_crop() -> None:
    case = CASES_BY_NAME["whorl_no_crop"]
    photo = case.photo()
    result = extract_fingerprint(photo, **case.params)
    assert case.params == {"crop": False}
    assert result.output_scale == 1.0
    assert result.image.shape == photo.shape[:2]


def test_output_scale_defaults_to_one() -> None:
    """Code that builds an ExtractionResult itself keeps working (the field has a default)."""
    result = ExtractionResult(image=np.zeros((4, 4), np.uint8), period=9.0, found_finger=True)
    assert result.output_scale == 1.0
