"""The grayscale twin of the print (PRD FR-37): the print's window and region, a soft tone, deterministic."""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from ridge import extract_fingerprint
from ridge.errors import NoRidgePatternError
from ridge.pipeline.imgutil import disk
from ridge.pipeline.render import GRAY_GAIN, PRINT_EDGE, binarize, render_gray
from tests.golden_cases import CASES_BY_NAME


def soft(signal: float) -> int:
    """The curve's 8-bit level for `signal` inside the region (hand computation in float64)."""
    x = signal / GRAY_GAIN
    return round(255 * (0.5 + 0.5 * x / math.sqrt(1 + x * x)))


def test_gray_is_zero_outside_the_print_region_and_fades_in() -> None:
    enh = np.full((5, 8), 1.4, np.float32)
    region = np.tile(np.linspace(0.0, 1.0, 8, dtype=np.float32), (5, 1))
    gray = render_gray(enh, region, flip=False)
    assert gray.dtype == np.uint8
    assert gray.shape == (5, 8)
    assert not gray[:, region[0] <= PRINT_EDGE].any()  # nothing where the print's region ends
    assert (np.diff(gray[0].astype(int)) >= 0).all()  # fades in towards the inside of the region
    assert gray[0, -1] == soft(1.4)
    assert (gray == gray[0]).all()


def test_gray_tone_is_a_soft_monotone_curve_of_the_signal() -> None:
    half = np.arange(1, 31, dtype=np.float32) * np.float32(0.1)
    x = np.concatenate([-half[::-1], [np.float32(0.0)], half])[None, :]
    gray = render_gray(x, np.ones_like(x), flip=False)[0].astype(int)
    assert (np.diff(gray) >= 0).all()
    assert gray[30] == 128  # no signal: mid-grey
    assert 0 < gray[0] < 40  # saturates softly, never fully
    assert 215 < gray[-1] < 255
    assert gray[40] == soft(1.0)
    flipped = render_gray(x, np.ones_like(x), flip=True)[0].astype(int)
    assert np.array_equal(flipped, gray[::-1])  # flipping the input mirrors the curve


def test_binarize_keeps_the_v0_rules_and_refuses_an_empty_region() -> None:
    enh = np.array([[1.0, -1.0, 1.0], [1.0, 1.0, -1.0]], np.float32)
    region = np.array([[1.0, 1.0, 0.4], [1.0, 1.0, 1.0]], np.float32)
    assert binarize(enh, region, 1.0, flip=False).tolist() == [[255, 0, 0], [255, 255, 0]]
    assert binarize(enh, region, 1.0, flip=True).tolist() == [[0, 255, 0], [0, 0, 255]]
    with pytest.raises(NoRidgePatternError):
        binarize(enh, np.zeros_like(region), 1.0, flip=False)


def test_pipeline_gray_is_the_prints_twin() -> None:
    photo = CASES_BY_NAME["whorl_default"].photo()
    result = extract_fingerprint(photo)
    gray, binary = result.gray, result.image
    assert gray is not None
    assert gray.shape == binary.shape
    assert gray.dtype == np.uint8
    ridges, valleys = binary > 0, binary == 0
    assert gray[ridges].mean() > 150
    assert gray[ridges].mean() > gray[valleys].mean() + 100
    assert len(np.unique(gray)) > 2  # a gradual tone, not another threshold
    # Nothing beyond the print: every non-zero grey pixel lies within two ridge spacings of a ridge.
    spacing = result.period * result.output_scale
    hull = cv2.dilate(binary, disk(4 * spacing)) > 0
    assert not gray[~hull].any()
    again = extract_fingerprint(photo)
    assert again.gray is not None
    assert np.array_equal(again.gray, gray)


def test_no_crop_frames_the_gray_like_the_print() -> None:
    photo = CASES_BY_NAME["whorl_default"].photo()
    result = extract_fingerprint(photo, crop=False)
    assert result.gray is not None
    assert result.gray.shape == result.image.shape == photo.shape[:2]
    assert result.gray[result.image > 0].mean() > result.gray[result.image == 0].mean()
    assert not result.gray[0].any()  # the frame outside the finger box stays black
