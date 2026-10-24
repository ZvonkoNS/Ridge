"""Finger silhouette from skin colour."""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask
from ridge.errors import NoRidgePatternError
from ridge.pipeline.imgutil import disk, fill_holes, largest_component


def finger_mask(bgr: ImageU8) -> Mask | None:
    """Finger silhouette from skin colour, or None if skin and background don't separate."""
    h, w = bgr.shape[:2]
    s = 512.0 / max(h, w)
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    a_u8 = cast(ImageU8, cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2LAB)[:, :, 1], (0, 0), 2))
    _, thresh = cv2.threshold(a_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    skin = thresh > 0
    # Otsu always splits the histogram; accept only a clear skin-vs-background split.
    if not 0.03 < skin.mean() < 0.97:
        return None
    a = cast(FloatImage, a_u8.astype(np.float32))
    contrast = a[skin].mean() - a[~skin].mean()
    separability = skin.mean() * (1 - skin.mean()) * contrast**2 / (a.var() + 1e-6)
    if separability < 0.75 or contrast < 5:
        return None
    opened = cv2.morphologyEx(skin.astype(np.uint8), cv2.MORPH_OPEN, disk(7))
    closed = cast(ImageU8, cv2.morphologyEx(opened, cv2.MORPH_CLOSE, disk(7)))
    filled = fill_holes(largest_component(closed))
    resized = cast(ImageU8, cv2.resize(filled.astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR))
    return resized > 0


SPECULAR_LEVEL = 250  # a pixel at or above this in any channel is a specular highlight (ADR-014 ``specular_mask``)


def without_specular(bgr: ImageU8, mask: Mask, period: float) -> tuple[Mask, float]:
    """Remove specular highlights, grown by half a ridge spacing, from the finger mask.

    Returns the reduced mask and the fraction of the finger area removed. Highlights carry no
    ridge signal and would otherwise skew the normalisation around them. Raises
    NoRidgePatternError when nothing of the finger is left.
    """
    bright = (bgr.max(axis=2) >= SPECULAR_LEVEL).astype(np.uint8)
    glare = cv2.dilate(bright, disk(period)) > 0  # disk diameter one spacing: half a spacing around each highlight
    fraction = float(glare[mask].mean()) if mask.any() else 0.0
    kept = mask & ~glare
    if not kept.any():
        raise NoRidgePatternError("the finger area is covered by specular highlights; nothing is left to process")
    return kept, fraction
