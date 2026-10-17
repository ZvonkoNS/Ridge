"""Ridge-quality map and selection of the area where a real ridge pattern is visible."""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8
from ridge.errors import NoRidgePatternError
from ridge.pipeline.imgutil import disk, fill_holes, largest_component, masked_blur

NO_RIDGES = "no clear ridge pattern found (try a lower --min-quality or a sharper photo)"


def periodicity(enh: FloatImage, phi: FloatImage, period: float) -> FloatImage:
    """Return ~1 where the ridge signal repeats one spacing away on both sides.

    Lone edges and creases (finger outline, background lines) give ~0.
    """
    energy = cv2.GaussianBlur(enh * enh, (0, 0), 0.5 * period)
    h, w = enh.shape
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    dx = (period * np.cos(phi)).astype(np.float32)
    dy = (period * np.sin(phi)).astype(np.float32)
    ahead = cv2.remap(energy, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    behind = cv2.remap(energy, xx - dx, yy - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return cast(FloatImage, np.clip(np.minimum(ahead, behind) / (energy + 1e-6), 0, 1))


def ridge_quality(
    enh: FloatImage, power: FloatImage, phi: FloatImage, mask: FloatImage, *, period: float, bank_power: float
) -> FloatImage:
    """Return ~1 for clean ridges and low values for noise.

    The share of the ridge-frequency energy that lies along the local ridge direction,
    counted only where that pattern repeats like ridges do.
    """
    quality = bank_power * masked_blur(enh * enh, mask, 1.5 * period) / (masked_blur(power, mask, 1.5 * period) + 1e-6)
    quality *= periodicity(enh, phi, period)
    return cast(FloatImage, cv2.GaussianBlur(quality * mask, (0, 0), 1.5 * period))


def print_region(quality: FloatImage, mask: FloatImage, period: float, min_quality: float) -> FloatImage:
    """Smooth 0..1 map of the single compact area kept as the print.

    Raises NoRidgePatternError when no area reaches `min_quality`.
    """
    inner = cv2.erode(mask.astype(np.uint8), disk(3 * period)) > 0  # skip the silhouette edge
    candidate = ((quality > min_quality) & inner).astype(np.uint8)
    # One compact blob: cut thin necks and lobes, then fill notches and holes.
    opened = cast(ImageU8, cv2.morphologyEx(candidate, cv2.MORPH_OPEN, disk(4 * period)))
    if not opened.any():
        raise NoRidgePatternError(NO_RIDGES)
    blob = largest_component(opened).astype(np.uint8)
    closed = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, disk(6 * period)) > 0
    filled = fill_holes(closed) & inner
    return cast(FloatImage, cv2.GaussianBlur(filled.astype(np.float32), (0, 0), 1.5 * period))  # smooth outline
