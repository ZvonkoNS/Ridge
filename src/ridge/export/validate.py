"""Argument checks shared by the export modules; every failure raises ``ParameterError``.

The checks take ``object`` so that they also protect callers that bypass the type checker
(library use, future RPC handlers).
"""

from __future__ import annotations

import math
from typing import Final, cast

import numpy as np

from ridge.arrays import ImageU8
from ridge.errors import ParameterError

MIN_PPI: Final = 1.0
MAX_PPI: Final = 100_000.0  # far above any scanner; keeps pHYs (uint32 pixels per metre) in range


def gray_u8(image: object, name: str = "image") -> ImageU8:
    """Return `image` if it is a non-empty H x W uint8 array, else raise ParameterError."""
    if not (isinstance(image, np.ndarray) and image.dtype == np.uint8 and image.ndim == 2 and image.size > 0):
        raise ParameterError(f"{name} must be a non-empty H x W uint8 (8-bit grayscale) array")
    return cast(ImageU8, image)


def finite(value: object, name: str) -> float:
    """Return `value` as a float if it is a finite real number (bool is refused)."""
    if isinstance(value, bool) or not isinstance(value, int | float | np.integer | np.floating):
        raise ParameterError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ParameterError(f"{name} must be finite")
    return number


def positive(value: object, name: str) -> float:
    """Return `value` as a float if it is finite and greater than zero."""
    number = finite(value, name)
    if number <= 0:
        raise ParameterError(f"{name} must be greater than 0")
    return number


def ppi_value(value: object, name: str = "ppi") -> float:
    """Return a resolution in pixels per inch within MIN_PPI..MAX_PPI."""
    number = positive(value, name)
    if not MIN_PPI <= number <= MAX_PPI:
        raise ParameterError(f"{name} must be between {MIN_PPI:g} and {MAX_PPI:g} pixels per inch")
    return number
