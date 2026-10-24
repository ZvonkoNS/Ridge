"""Output rendering of the filtered ridge signal: the print and its grayscale twin (pure, no I/O).

The pipeline's Gabor output is a smooth, signed ridge signal at working scale: positive on
ridges, negative in valleys, about +-1.4 on clean ridges (the normalised photo has unit local
standard deviation and the bank has unit gain for a matching ridge wave). The same window of it,
resized to output size, is rendered twice:

* the **print** (PRD FR-1): the sign of the signal inside the kept region, white ridges on
  black, specks removed; exactly the v0 result;
* the **grayscale print** (PRD FR-37): the signal through a soft contrast curve, so ridge
  strength survives. It is the un-thresholded twin of the print: same window, same size, same
  filter output, and it is zero wherever the print's region ends, so it can show no ridge the
  print does not show. What it adds is the gradual tone of an inked impression, which
  fingerprint feature extractors and NFIQ 2 are built for and a thresholded image denies them.

The curve is the algebraic sigmoid x / sqrt(1 + x^2), not tanh: it needs only IEEE 754
arithmetic (no libm transcendental), so it is bit-reproducible per CPU architecture like the
rest of the pipeline (NFR-3, ADR-009). Both renderings are method constants of the published
algorithm; changing them is a method change (forensic standard section 6).
"""

from __future__ import annotations

from typing import Final, cast

import numpy as np

from ridge.arrays import FloatImage, ImageU8
from ridge.errors import NoRidgePatternError
from ridge.pipeline.imgutil import remove_specks
from ridge.pipeline.quality import NO_RIDGES

# Signal value that maps to 1/sqrt(2) ~ 71 % of full contrast; clean ridges (+-1.4) reach ~94 %, so
# ridge tops are nearly flat like ink while weak ridges keep visible gradation.
GRAY_GAIN: Final = 0.5
# The print's region is `region > PRINT_EDGE` (quality.print_region is a 0..1 map); the grayscale
# print fades in from that edge to full tone where the map reaches 1.
PRINT_EDGE: Final = 0.5


def binarize(enh_out: FloatImage, region_out: FloatImage, p_out: float, *, flip: bool) -> ImageU8:
    """Threshold the filter output inside the print region: white ridges (255) on black (0).

    `enh_out` and `region_out` are H x W float32 at output size; `p_out` is the output ridge
    spacing in pixels (specks smaller than a quarter of a ridge-spacing square are removed).
    Raises NoRidgePatternError when no pixel of the region reaches the output.
    """
    kept_region = region_out > PRINT_EDGE
    if not kept_region.any():
        raise NoRidgePatternError(NO_RIDGES)
    ridges = (enh_out < 0) if flip else (enh_out > 0)  # ridges are the bright lines in a photo
    kept = remove_specks(ridges & kept_region, min_area=0.25 * p_out * p_out)
    return kept.astype(np.uint8) * 255


def render_gray(enh_out: FloatImage, region_out: FloatImage, *, flip: bool) -> ImageU8:
    """Map the filter output through a soft contrast curve: bright ridges, dark valleys, 0 outside.

    `enh_out` and `region_out` are H x W float32 at output size (as for `binarize`). The result is
    H x W uint8: 0 where `region_out` is at or below PRINT_EDGE, fading in to the full curve where
    the region map reaches 1; the curve maps a signal of 0 to mid-grey and saturates softly.
    """
    signal = -enh_out if flip else enh_out
    x = signal / np.float32(GRAY_GAIN)
    soft = x / np.sqrt(np.float32(1.0) + x * x)  # algebraic sigmoid in (-1, 1), float32 throughout
    tone = np.float32(0.5) + np.float32(0.5) * soft
    inner = np.clip((region_out - np.float32(PRINT_EDGE)) / np.float32(1.0 - PRINT_EDGE), 0.0, 1.0)
    gray = np.rint(tone * inner.astype(np.float32) * np.float32(255.0))
    return cast(ImageU8, np.clip(gray, 0, 255).astype(np.uint8))
