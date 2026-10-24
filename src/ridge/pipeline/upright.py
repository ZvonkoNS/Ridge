"""Rotation of the finger to upright before extraction (ADR-014 variant ``upright``; pure, no I/O).

AFIS operators expect a fingertip pointing up, and an examiner compares more easily when every
print has the same orientation. The finger's axis comes from the second moments of the skin
mask; the tip is the narrower end (a fingertip tapers). When both ends are alike, the end
farther from the photo's border is the tip (a finger enters the frame from the hand's side), and
when that is a tie too, the smaller rotation wins. The photo is rotated once (bilinear), the mask
with it (nearest), onto a canvas that holds the whole photo; the print location is mapped back
to the photo's pixels through the inverse transform, so the report still says where the print
came from. Rotation resamples the photo before extraction: a method change, recorded in the
report, off by default.
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

MIN_AXIS_PIXELS: Final = 64  # a smaller mask has no reliable axis
END_SHARE: Final = 0.15  # the share of the finger's length counted as each end
TAPER_RATIO: Final = 0.9  # an end with less than this share of the other end's area is the tip
BORDER_TIE_PX: Final = 2.0  # ends this close to equally far from the border are a tie
MAX_ROTATED_PIXELS: Final = 250_000_000  # bound on the rotated canvas (CWE-789)

Points = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Rotation:
    """The rotation applied to put the finger upright.

    `angle_deg` follows OpenCV (counter-clockwise on screen); `matrix` is the 2 x 3 affine from photo
    pixels to canvas pixels; `size` is the canvas (width, height) that holds the whole rotated photo.
    """

    angle_deg: float
    matrix: NDArray[np.float64]
    size: tuple[int, int]


def _normalised(angle: float) -> float:
    """Return `angle` in degrees within (-180, 180]."""
    wrapped = (angle + 180.0) % 360.0 - 180.0
    return 180.0 if wrapped == -180.0 else wrapped


def rotation_angle(ux: float, uy: float) -> float:
    """Degrees that turn the unit direction (ux, uy) towards the tip into "up" (0, -1), OpenCV convention."""
    return _normalised(math.degrees(math.atan2(uy, ux)) + 90.0)


def _tip_sign(mask: Mask, cx: float, cy: float, ux: float, uy: float) -> int:
    """Return +1 when the tip lies towards +u, -1 towards -u: taper, then border distance, then the smaller turn."""
    ys, xs = np.nonzero(mask)
    proj = (xs - cx) * ux + (ys - cy) * uy
    lo, hi = float(proj.min()), float(proj.max())
    span = hi - lo
    area_hi = int(np.count_nonzero(proj >= hi - END_SHARE * span))
    area_lo = int(np.count_nonzero(proj <= lo + END_SHARE * span))
    if area_hi < TAPER_RATIO * area_lo:
        return 1
    if area_lo < TAPER_RATIO * area_hi:
        return -1
    h, w = mask.shape

    def border(px: float, py: float) -> float:
        return float(min(px, py, w - 1 - px, h - 1 - py))

    d_hi, d_lo = border(cx + hi * ux, cy + hi * uy), border(cx + lo * ux, cy + lo * uy)
    if abs(d_hi - d_lo) > BORDER_TIE_PX:
        return 1 if d_hi > d_lo else -1
    return 1 if abs(rotation_angle(ux, uy)) <= abs(rotation_angle(-ux, -uy)) else -1


def finger_axis(mask: Mask) -> tuple[float, float, float, float] | None:
    """Return (cx, cy, ux, uy): the mask's centroid and unit direction towards the tip; None without a clear axis."""
    m = cv2.moments(mask.astype(np.uint8), binaryImage=True)
    if m["m00"] < MIN_AXIS_PIXELS:
        return None
    cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    mu20, mu02, mu11 = m["mu20"] / m["m00"], m["mu02"] / m["m00"], m["mu11"] / m["m00"]
    if abs(mu20 - mu02) < 1e-9 and abs(mu11) < 1e-9:
        return None  # round: no axis to speak of
    theta = 0.5 * math.atan2(2.0 * mu11, mu20 - mu02)
    ux, uy = math.cos(theta), math.sin(theta)
    if not np.ptp((np.nonzero(mask)[1] - cx) * ux + (np.nonzero(mask)[0] - cy) * uy) > 0:
        return None
    sign = _tip_sign(mask, cx, cy, ux, uy)
    return cx, cy, sign * ux, sign * uy


def upright_rotation(mask: Mask) -> Rotation | None:
    """Return the rotation that puts the finger's axis vertical with the tip up, or None when the mask has no axis."""
    axis = finger_axis(mask)
    if axis is None:
        return None
    cx, cy, ux, uy = axis
    angle = rotation_angle(ux, uy)
    h, w = mask.shape
    matrix = np.asarray(cv2.getRotationMatrix2D((cx, cy), angle, 1.0), dtype=np.float64)
    corners = np.array([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]], dtype=np.float64)
    mapped = corners @ matrix[:, :2].T + matrix[:, 2]
    low, high = mapped.min(axis=0), mapped.max(axis=0)
    size = (math.ceil(high[0] - low[0]), math.ceil(high[1] - low[1]))
    if size[0] * size[1] > MAX_ROTATED_PIXELS:
        raise WorkAreaTooLargeError("the photo is too large to rotate to upright; crop it to the finger first")
    matrix[0, 2] -= low[0]
    matrix[1, 2] -= low[1]
    return Rotation(angle, matrix, size)


def rotate_bgr(bgr: ImageU8, rotation: Rotation) -> ImageU8:
    """Rotate a BGR photo onto the canvas (bilinear; the uncovered canvas is black)."""
    rotated = cv2.warpAffine(
        bgr,
        rotation.matrix,
        rotation.size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    return cast(ImageU8, rotated)


def rotate_mask(mask: Mask, rotation: Rotation) -> Mask:
    """Rotate a boolean mask onto the canvas (nearest neighbour)."""
    rotated = cv2.warpAffine(
        mask.astype(np.uint8), rotation.matrix, rotation.size, flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT
    )
    return rotated > 0


def to_photo(points: Points, rotation: Rotation) -> Points:
    """Map N x 2 canvas coordinates back to the photo's coordinates (the inverse affine)."""
    inverse = np.asarray(cv2.invertAffineTransform(rotation.matrix), dtype=np.float64)
    return points @ inverse[:, :2].T + inverse[:, 2]
