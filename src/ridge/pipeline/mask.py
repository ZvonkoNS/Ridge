"""Finger silhouette from skin colour."""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask
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
