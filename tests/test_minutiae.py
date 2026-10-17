"""Minutiae extraction on synthetic ridge drawings with known minutiae (PRD FR-40)."""

from __future__ import annotations

import math
import time

import cv2
import numpy as np
import pytest

from ridge import extract_fingerprint
from ridge.errors import ParameterError
from ridge.minutiae import Minutia, MinutiaeResult, crossing_number, extract_minutiae, thin, to_export_space
from tests.golden_cases import CASES_BY_NAME

SPACING = 16  # ridge spacing of the drawings
ROWS = range(36, 170, SPACING)  # ridge centre lines (y) for a 200 x 200 drawing


def drawing(lines: list[tuple[tuple[int, int], tuple[int, int]]]) -> np.ndarray:
    img = np.zeros((200, 200), np.uint8)
    for p1, p2 in lines:
        cv2.line(img, p1, p2, 255, thickness=5)
    return img


def parallel(skip: int | None = None) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    return [((0, y), (199, y)) for y in ROWS if y != skip]


def angle_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def test_thinning_gives_one_pixel_lines() -> None:
    img = drawing([((20, 100), (180, 100))])
    skel = thin(img > 0)
    assert skel.any()
    assert not (skel & ~(img > 0)).any()  # the skeleton lies inside the ridge
    assert int(skel[:, 40:160].sum(axis=0).max()) == 1  # one pixel per column along the line


def test_crossing_numbers_of_end_and_fork() -> None:
    skel = np.zeros((20, 20), bool)
    skel[10, 2:10] = True  # stem
    for i in range(1, 6):
        skel[10 - i, 9 + i] = True  # upper branch
        skel[10 + i, 9 + i] = True  # lower branch
    cn = crossing_number(skel)
    assert cn[10, 2] == 1
    assert cn[10, 9] == 3


def test_parallel_ridges_have_no_minutiae() -> None:
    assert extract_minutiae(drawing(parallel()), SPACING).minutiae == ()


def test_ridge_ending_is_found_with_direction() -> None:
    lines = [*parallel(skip=100), ((0, 100), (100, 100))]  # the middle ridge stops at x = 100
    found = extract_minutiae(drawing(lines), SPACING).minutiae
    assert [m.kind for m in found] == ["ending"]
    ending = found[0]
    assert math.hypot(ending.x - 100, ending.y - 100) <= 4
    assert angle_gap(ending.angle_deg, 0.0) <= 20  # points away from the ridge, to the right


def test_bifurcation_is_found_with_direction() -> None:
    fork_arms = [((100, 100), (130, 92)), ((130, 92), (199, 92)), ((100, 100), (130, 108)), ((130, 108), (199, 108))]
    lines = [*parallel(skip=100), ((0, 100), (100, 100)), *fork_arms]
    found = extract_minutiae(drawing(lines), SPACING).minutiae
    assert [m.kind for m in found] == ["bifurcation"]
    fork = found[0]
    # The valley between the arms (and so the fork) opens a few pixels after the drawn junction,
    # once the 5 px wide arms have separated.
    assert math.hypot(fork.x - 108, fork.y - 100) <= 8
    assert angle_gap(fork.angle_deg, 0.0) <= 20  # into the fork, to the right


def test_broken_ridge_is_not_two_endings() -> None:
    lines = [*parallel(skip=100), ((0, 100), (96, 100)), ((104, 100), (199, 100))]  # 8 px gap < one spacing
    assert extract_minutiae(drawing(lines), SPACING).minutiae == ()


def test_export_space_mapping() -> None:
    result = MinutiaeResult((Minutia(10, 20, "ending", 0.0, 50),), width=100, height=50, ridge_period_px=10.0)
    moved = to_export_space(result, factor=2.0, mirrored=True)
    assert moved.minutiae[0] == Minutia(178, 40, "ending", 180.0, 50)
    assert (moved.width, moved.height, moved.ridge_period_px) == (200, 100, 20.0)
    with pytest.raises(ParameterError):
        to_export_space(result, factor=0.0, mirrored=False)


def test_json_template() -> None:
    lines = [*parallel(skip=100), ((0, 100), (100, 100))]
    doc = extract_minutiae(drawing(lines), SPACING).to_json()
    assert doc["schema"] == "ridge.minutiae/1"
    assert doc["image"] == {"width": 200, "height": 200, "space": "print"}
    assert set(doc["minutiae"][0]) == {"x", "y", "type", "angle_deg", "quality"}
    assert 1 <= doc["minutiae"][0]["quality"] <= 100


@pytest.mark.parametrize(
    ("image", "period"),
    [
        (np.zeros((50, 50, 3), np.uint8), 10.0),
        (np.zeros((50, 50), np.float32), 10.0),
        (np.zeros((50, 50), np.uint8), 1.0),
        (np.zeros((50, 50), np.uint8), float("nan")),
    ],
)
def test_invalid_arguments(image: np.ndarray, period: float) -> None:
    with pytest.raises(ParameterError):
        extract_minutiae(image, period)


def test_runs_on_a_pipeline_print_quickly() -> None:
    result = extract_fingerprint(CASES_BY_NAME["whorl_default"].photo())
    start = time.perf_counter()
    found = extract_minutiae(result.image, result.period * result.output_scale)
    assert time.perf_counter() - start < 10
    h, w = result.image.shape
    for m in found.minutiae:
        assert 0 <= m.x < w
        assert 0 <= m.y < h
        assert m.kind in ("ending", "bifurcation")
