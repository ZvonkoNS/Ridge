"""Rectification of the finger pad's curvature (ADR-014 variant ``rectify``; pure).

A finger pad is roughly a cylinder. Photographed from the front, the ridges near its sides are
foreshortened: a patch of skin turned by an angle theta from the camera axis appears cos(theta) as
wide, so the ridge spacing shrinks towards the edges, and the bank tuned to the central spacing and
the periodicity check rate those areas poorly. This variant unrolls the pad: each row of the upright
finger is treated as a half-circle whose radius is the finger's half-width in that row (smoothed
along the finger), and the pixel at offset x from the centre line moves to the arc length
w * asin(x / w), up to MAX_ANGLE_DEG where the surface turns away from the camera. The centre line
keeps the photo's scale; the sides are stretched by 1 / cos(theta). Rows are unchanged, so the
variant works on an upright finger (it implies the upright rotation). Unvalidated, off by default,
recorded in the report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from ridge.arrays import ImageU8, Mask
from ridge.errors import WorkAreaTooLargeError

MAX_ANGLE_DEG: Final = 70.0  # the pad is unrolled up to this surface angle; beyond it the ridges are not resolvable
MAX_ANGLE: Final = math.radians(MAX_ANGLE_DEG)
MIN_ROWS: Final = 64  # a shorter finger has no usable width profile
MIN_HALF_WIDTH: Final = 8.0  # rows narrower than this (the tip's cap, mask noise) take the neighbouring width
SMOOTH_SHARE: Final = 0.03  # sigma of the smoothing along the finger, as a share of its length in rows
MAX_RECTIFIED_PIXELS: Final = 50_000_000  # bound on the unrolled canvas and its two float maps (CWE-789)

Points = NDArray[np.float64]
Profile = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Rectification:
    """Per-row geometry of the unrolled finger.

    `centre[y]` and `half_width[y]` describe the finger in row y of the source canvas; `size` is the
    unrolled canvas (width, height) and `middle` the canvas column the centre line maps to.
    """

    centre: Profile
    half_width: Profile
    size: tuple[int, int]
    middle: float
    rows: NDArray[np.bool_]  # the source rows that hold finger (the others carry the nearest row's geometry)

    @property
    def half_width_px(self) -> float:
        """The median half-width over the rows that hold finger, for the report (background rows do not count)."""
        return float(np.median(self.half_width[self.rows]))


def _smoothed(values: Profile, sigma: float) -> Profile:
    """Gaussian smoothing along the finger with edge values held at both ends."""
    radius = max(1, int(3 * sigma))
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    padded = np.pad(values, radius, mode="edge")
    return cast(Profile, np.convolve(padded, kernel / kernel.sum(), mode="valid"))


def width_profile(mask: Mask) -> tuple[Profile, Profile, NDArray[np.bool_]] | None:
    """Return the centre line and half-width per row (smoothed) and the rows that hold finger; None when too short."""
    filled = mask.any(axis=1)
    rows = np.flatnonzero(filled)
    if rows.size < MIN_ROWS:
        return None
    left = mask.argmax(axis=1).astype(np.float64)
    right = (mask.shape[1] - 1 - mask[:, ::-1].argmax(axis=1)).astype(np.float64)
    centre, half = (left + right) / 2.0, (right - left + 1) / 2.0
    valid = filled & (half >= MIN_HALF_WIDTH)
    if not valid.any():
        return None
    index = np.arange(mask.shape[0], dtype=np.float64)
    good = np.flatnonzero(valid)
    centre = np.interp(index, index[good], centre[good])  # rows without a usable width take the nearest one's
    half = np.interp(index, index[good], half[good])
    sigma = max(1.0, SMOOTH_SHARE * rows.size)
    return _smoothed(centre, sigma), _smoothed(half, sigma), filled


def rectification(mask: Mask) -> Rectification | None:
    """Plan the unrolling of the finger in `mask` (upright: axis vertical); None when it cannot be planned."""
    profile = width_profile(mask)
    if profile is None:
        return None
    centre, half, filled = profile
    middle = float(math.ceil(float(half.max()) * MAX_ANGLE) + 1)
    width, height = int(2 * middle), mask.shape[0]
    if width * height > MAX_RECTIFIED_PIXELS:
        raise WorkAreaTooLargeError("the finger is too large to rectify; crop the photo to the finger")
    return Rectification(centre, half, (width, height), middle, filled)


def _maps(r: Rectification) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Source coordinates of every canvas pixel (for cv2.remap); -1 outside the unrolled pad."""
    width, height = r.size
    theta = (np.arange(width, dtype=np.float32) - np.float32(r.middle))[None, :] / r.half_width.astype(np.float32)[
        :, None
    ]
    inside = np.abs(theta) <= np.float32(MAX_ANGLE)
    x = r.centre.astype(np.float32)[:, None] + r.half_width.astype(np.float32)[:, None] * np.sin(theta)
    rows = np.repeat(np.arange(height, dtype=np.float32)[:, None], width, axis=1)
    return np.where(inside, x, np.float32(-1)), np.where(inside, rows, np.float32(-1))


def rectify_bgr(bgr: ImageU8, r: Rectification) -> ImageU8:
    """Unroll a BGR canvas (bilinear; outside the pad the canvas is black)."""
    mapx, mapy = _maps(r)
    out = cv2.remap(bgr, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    return cast(ImageU8, out)


def rectify_mask(mask: Mask, r: Rectification) -> Mask:
    """Unroll a boolean mask (nearest neighbour)."""
    mapx, mapy = _maps(r)
    out = cv2.remap(mask.astype(np.uint8), mapx, mapy, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
    return out > 0


def _rows(points: Points, r: Rectification) -> NDArray[np.intp]:
    return np.clip(np.rint(points[:, 1]), 0, r.size[1] - 1).astype(np.intp)


def to_source(points: Points, r: Rectification) -> Points:
    """Map N x 2 canvas coordinates back to the upright canvas they were unrolled from (rows unchanged)."""
    rows = _rows(points, r)
    half, centre = r.half_width[rows], r.centre[rows]
    theta = np.clip((points[:, 0] - r.middle) / half, -MAX_ANGLE, MAX_ANGLE)
    return np.column_stack([centre + half * np.sin(theta), points[:, 1]])


def to_canvas(points: Points, r: Rectification) -> Points:
    """Map N x 2 upright-canvas coordinates onto the unrolled canvas (the inverse of `to_source`)."""
    rows = _rows(points, r)
    half, centre = r.half_width[rows], r.centre[rows]
    u = np.clip((points[:, 0] - centre) / half, -math.sin(MAX_ANGLE), math.sin(MAX_ANGLE))
    return np.column_stack([r.middle + half * np.arcsin(u), points[:, 1]])
