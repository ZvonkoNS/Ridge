"""The single-channel image the pipeline works on (ADR-014 variant ``channel``; pure, no I/O).

The characterised pipeline reads the green plane: on skin, green shows ridges best for most
cameras. Other planes can carry more ridge contrast for some skin tones and some lighting, so
the examiner may choose one, or let Ridge pick the plane whose patch spectra show the sharpest
ridge peak (`ridge_signal_strength`). The choice is deterministic and is recorded in the report.
"""

from __future__ import annotations

from typing import Final, cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask
from ridge.pipeline.options import Channel
from ridge.pipeline.period import ridge_signal_strength

PLANES: Final[dict[str, int]] = {"blue": 0, "green": 1, "red": 2}  # BGR indices
AUTO_ORDER: Final = ("green", "red", "blue", "luma")  # ties keep the earlier one: green stays the default


def plane(bgr: ImageU8, name: str) -> FloatImage:
    """Return one plane of a BGR uint8 photo as float32 in [0, 1] (``luma`` is BT.601 luminance)."""
    if name == "luma":
        return cast(FloatImage, cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0)
    return cast(FloatImage, bgr[:, :, PLANES[name]].astype(np.float32) / 255.0)


def gray_channel(bgr: ImageU8, channel: Channel, mask: Mask) -> tuple[FloatImage, str]:
    """Return the plane the pipeline works on and its name (``auto`` resolved to the plane used)."""
    if channel != "auto":
        return plane(bgr, channel), channel
    best_name, best_plane, best_strength = AUTO_ORDER[0], plane(bgr, AUTO_ORDER[0]), -1.0
    for name in AUTO_ORDER:
        candidate = plane(bgr, name)
        strength = ridge_signal_strength(candidate, mask)
        if strength > best_strength:  # strictly greater: a tie keeps the earlier plane
            best_name, best_plane, best_strength = name, candidate, strength
    return best_plane, best_name
