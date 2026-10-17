"""Thinning of a binary ridge image to a one-pixel-wide skeleton (Zhang & Suen, 1984).

Vectorised with NumPy: every sub-iteration evaluates all pixels at once on the padded image.
The result is deterministic (no randomness, fixed pixel order not needed) and bounded: at most
``max_iterations`` passes, enough for ridges far wider than Ridge produces.
"""

from __future__ import annotations

from typing import cast

import numpy as np

from ridge.arrays import Mask

MAX_ITERATIONS = 100


def _neighbours(img: np.ndarray) -> list[np.ndarray]:
    """P2..P9 of every pixel (clockwise from north), as int arrays the size of `img`."""
    p = np.pad(img, 1).astype(np.int8)
    h, w = img.shape
    return [
        p[0:h, 1 : w + 1],  # P2 north
        p[0:h, 2 : w + 2],  # P3 north-east
        p[1 : h + 1, 2 : w + 2],  # P4 east
        p[2 : h + 2, 2 : w + 2],  # P5 south-east
        p[2 : h + 2, 1 : w + 1],  # P6 south
        p[2 : h + 2, 0:w],  # P7 south-west
        p[1 : h + 1, 0:w],  # P8 west
        p[0:h, 0:w],  # P9 north-west
    ]


def thin(binary: Mask, max_iterations: int = MAX_ITERATIONS) -> Mask:
    """Return the Zhang-Suen skeleton of a boolean ridge image (ridges True)."""
    img = binary.astype(bool).copy()
    for _ in range(max_iterations):
        changed = False
        for step in (0, 1):
            n = _neighbours(img)
            count = sum(n)  # B(P1): number of ridge neighbours
            seq = [*n, n[0]]
            transitions = sum((seq[i] == 0) & (seq[i + 1] == 1) for i in range(8))  # A(P1)
            p2, p4, p6, p8 = n[0], n[2], n[4], n[6]
            first = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            second = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            cond = first if step == 0 else second
            remove = img & (count >= 2) & (count <= 6) & (transitions == 1) & cond
            if remove.any():
                img[remove] = False
                changed = True
        if not changed:
            break
    return cast(Mask, img)


def crossing_number(skeleton: Mask) -> np.ndarray:
    """Crossing number of every skeleton pixel: 1 ridge ending, 2 ridge, 3 bifurcation (0 off-skeleton)."""
    n = _neighbours(skeleton)
    seq = [*n, n[0]]
    cn = sum(np.abs(seq[i].astype(np.int16) - seq[i + 1]) for i in range(8)) // 2
    return np.where(skeleton, cn, 0)
