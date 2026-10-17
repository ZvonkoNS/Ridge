"""Deterministic synthetic finger photos for tests.

No real biometric data is ever used in the repository: every test image is generated here
from closed-form ridge patterns plus seeded noise, so the fixtures are reproducible on every
platform and carry no personal data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

ImageU8 = NDArray[np.uint8]
FloatArray = NDArray[np.float32]

SKIN_BGR = np.array([120.0, 150.0, 210.0], dtype=np.float32)
BACKGROUND_BGR = np.array([150.0, 140.0, 125.0], dtype=np.float32)


def _grid(height: int, width: int) -> tuple[FloatArray, FloatArray]:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    return yy, xx


def whorl_pattern(height: int, width: int, period: float) -> FloatArray:
    """Concentric, slightly warped ellipses: a whorl-like ridge field in [0, 1]."""
    yy, xx = _grid(height, width)
    cx, cy = width / 2.0, height / 2.0
    r = np.sqrt((xx - cx) ** 2 + ((yy - cy - 0.05 * height) / 1.35) ** 2)
    r += 0.33 * period * np.sin(3.0 * np.arctan2(yy - cy, xx - cx))
    return (0.5 + 0.5 * np.cos(2.0 * np.pi * r / period)).astype(np.float32)


def arch_pattern(height: int, width: int, period: float) -> FloatArray:
    """Wavy horizontal ridges: an arch-like ridge field in [0, 1]."""
    yy, xx = _grid(height, width)
    bend = 0.12 * height * np.exp(-(((xx - width / 2.0) / (0.3 * width)) ** 2))
    return (0.5 + 0.5 * np.cos(2.0 * np.pi * (yy + bend) / period)).astype(np.float32)


def noise_pattern(height: int, width: int, period: float, seed: int = 7) -> FloatArray:
    """Smoothed noise with no ridge structure."""
    rng = np.random.default_rng(seed)
    noise = rng.random((height, width), dtype=np.float32)
    return cast(FloatArray, cv2.GaussianBlur(noise, (0, 0), 0.4 * period))


def finger_photo(
    pattern: FloatArray,
    *,
    colour: bool = True,
    seed: int = 0,
    noise_sigma: float = 6.0,
    blur_sigma: float = 1.0,
) -> ImageU8:
    """Render a ridge field as a BGR photo of a finger (ellipse) on a plain background."""
    height, width = pattern.shape
    yy, xx = _grid(height, width)
    finger = ((xx - width / 2.0) / (0.32 * width)) ** 2 + ((yy - height / 2.0) / (0.40 * height)) ** 2 <= 1.0
    light = (0.75 + 0.25 * (xx / width))[..., None]
    shade = (0.8 + 0.25 * pattern)[..., None]
    if colour:
        img = np.where(finger[..., None], SKIN_BGR * shade, BACKGROUND_BGR)
    else:
        img = np.where(finger[..., None], 170.0 * shade, 120.0) * np.ones(3, np.float32)
    rng = np.random.default_rng(seed)
    img = img * light + rng.normal(0.0, noise_sigma, (height, width, 1)).astype(np.float32)
    img_u8 = np.clip(img, 0, 255).astype(np.uint8)
    return cast(ImageU8, cv2.GaussianBlur(img_u8, (0, 0), blur_sigma))


PATTERNS: dict[str, Callable[[int, int, float], FloatArray]] = {
    "whorl": whorl_pattern,
    "arch": arch_pattern,
    "noise": noise_pattern,
}


def make_photo(pattern: str, height: int, width: int, period: float, *, colour: bool = True) -> ImageU8:
    """Build a named synthetic photo, e.g. ``make_photo("whorl", 480, 360, 9.0)``."""
    return finger_photo(PATTERNS[pattern](height, width, period), colour=colour)
