"""Small image-processing helpers used by the extraction pipeline (pure functions)."""

from __future__ import annotations

from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask


def masked_blur(img: FloatImage, mask: FloatImage, sigma: float) -> FloatImage:
    """Gaussian blur that only averages pixels inside `mask` (no halos at the finger edge)."""
    num = cv2.GaussianBlur(img * mask, (0, 0), sigma)
    den = cv2.GaussianBlur(mask, (0, 0), sigma)
    return cast(FloatImage, num / np.maximum(den, 1e-3))


def disk(diameter: float) -> ImageU8:
    """Elliptical structuring element with an odd size of at least 3 pixels."""
    d = max(3, round(diameter) | 1)
    return cast(ImageU8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d)))


def largest_component(mask: Mask | ImageU8) -> Mask:
    """Keep only the largest 8-connected component of a binary mask."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 1:
        return mask.astype(bool)
    return cast(Mask, labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])))


def fill_holes(mask: Mask) -> Mask:
    """Fill regions of a mask that are not connected to the image border."""
    _, labels = cv2.connectedComponents((~mask).astype(np.uint8), connectivity=4)
    outside = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    return mask | ~np.isin(labels, outside)


def remove_specks(binary: Mask, min_area: float) -> Mask:
    """Drop 8-connected components smaller than `min_area` pixels."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    return cast(Mask, keep[labels])
