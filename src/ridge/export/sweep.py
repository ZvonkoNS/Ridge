"""Scale sweep for comparison exports whose scale is only estimated (PRD FR-39; pure, no I/O).

Minutiae matching tolerates little scale error, so an AFIS search of a photographed print whose
scale is estimated is often run at a few scales. A sweep takes one export and rescales it by
factors spread evenly over the export's recorded scale uncertainty (for ±15 % and three steps:
0.85, 1.00, 1.15). Every file is still declared at the export's resolution, so an AFIS reads them
as images of different physical size, and they are submitted as separate searches. Ridge records
every file; it matches or ranks nothing.
"""

from __future__ import annotations

from typing import Final, cast

import cv2
import numpy as np

from ridge.arrays import ImageU8
from ridge.errors import ExportTooLargeError, ParameterError
from ridge.export.transforms import MAX_EXPORT_PIXELS
from ridge.export.validate import finite, gray_u8, positive

MIN_STEPS: Final = 3
MAX_STEPS: Final = 9
MAX_SWEEP_UNCERTAINTY_PCT: Final = 50.0  # beyond this the "scale" is not an estimate any more
DEFAULT_STEPS: Final = 3


def sweep_factors(uncertainty_pct: float, steps: int = DEFAULT_STEPS) -> tuple[float, ...]:
    """Return factors from 1 - u to 1 + u in `steps` equal steps (odd, 3..9), with 1.0 in the middle.

    `uncertainty_pct` is the export's recorded relative scale uncertainty; it must be above 0 (an
    exact scale needs no sweep) and at most MAX_SWEEP_UNCERTAINTY_PCT. Factors are rounded to four
    decimals so file names and records agree on every platform.
    """
    uncertainty = finite(uncertainty_pct, "uncertainty_pct")
    if not 0.0 < uncertainty <= MAX_SWEEP_UNCERTAINTY_PCT:
        raise ParameterError(
            f"a sweep needs a scale uncertainty above 0 and at most {MAX_SWEEP_UNCERTAINTY_PCT:g} %; "
            f"this export records {uncertainty:g} %"
        )
    count: object = steps  # callers that bypass the type checker still get a clear refusal
    if isinstance(count, bool) or not isinstance(count, int) or not MIN_STEPS <= count <= MAX_STEPS or count % 2 == 0:
        raise ParameterError(f"steps must be an odd number from {MIN_STEPS} to {MAX_STEPS}")
    half = (steps - 1) // 2
    factors = tuple(round(1.0 + (i / half) * uncertainty / 100.0, 4) for i in range(-half, half + 1))
    if len(set(factors)) != len(factors):  # two steps would get the same factor and the same file name
        raise ParameterError(
            f"a scale uncertainty of {uncertainty:g} % is too small to tell {steps} steps apart; use fewer steps"
        )
    return factors


def rescaled(image: ImageU8, factor: float) -> ImageU8:
    """Resample an H x W uint8 image by `factor`: area averaging when shrinking, bicubic when enlarging.

    The same interpolation as the 500 ppi scaling (``ridge.export.transforms.to_ppi``); the size is
    rounded to whole pixels. Raises ExportTooLargeError beyond MAX_EXPORT_PIXELS.
    """
    src = gray_u8(image)
    f = positive(factor, "factor")
    height, width = src.shape
    size = (max(1, round(width * f)), max(1, round(height * f)))
    if size[0] * size[1] > MAX_EXPORT_PIXELS:
        raise ExportTooLargeError(f"at factor {f:g} the image would be {size[0]}x{size[1]} px; check the scale")
    if f == 1.0:
        return src.copy()
    interpolation = cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(src.astype(np.float32), size, interpolation=interpolation)
    return cast(ImageU8, np.clip(np.rint(resized), 0, 255).astype(np.uint8))
