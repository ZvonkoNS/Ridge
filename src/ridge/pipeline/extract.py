"""Extraction pipeline: photo of a finger in, white-on-black fingerprint out (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask
from ridge.errors import NoRidgePatternError, ParameterError, ResolutionTooLowError, WorkAreaTooLargeError
from ridge.pipeline.gabor import gabor_bank, oriented_filter, ridge_orientation
from ridge.pipeline.imgutil import masked_blur, remove_specks
from ridge.pipeline.mask import finger_mask
from ridge.pipeline.period import estimate_period
from ridge.pipeline.quality import NO_RIDGES, print_region, ridge_quality

WORK_PERIOD = 12.0  # ridge spacing in pixels that the photo is rescaled to for filtering
MIN_PERIOD = 3.0  # below this the ridges cannot be resolved
MAX_WORK_PIXELS = 40_000_000  # memory bound for the rescaled finger area (CWE-789)


@dataclass(frozen=True)
class DebugImages:
    """Intermediate images for review: what the pipeline saw at each step."""

    region: ImageU8  # BGR crop of the photo with the used area outlined in green
    normalized: ImageU8
    gabor: ImageU8
    quality: ImageU8


@dataclass(frozen=True)
class ExtractionResult:
    """White-on-black fingerprint plus what was measured on the way."""

    image: ImageU8
    period: float  # ridge spacing in pixels in the photo
    found_finger: bool  # False: skin colour did not separate, the whole photo was searched
    debug: DebugImages | None = None


def _check_arguments(bgr: object, period: float | None, min_quality: float) -> None:
    """Validate library-call arguments (the CLI validates too, but callers may not)."""
    if not (isinstance(bgr, np.ndarray) and bgr.dtype == np.uint8 and bgr.ndim == 3 and bgr.shape[2] == 3):
        raise ParameterError("bgr must be an H x W x 3 uint8 array")
    if period is not None and not (np.isfinite(period) and period > 0):
        raise ParameterError("period must be a positive, finite number of pixels")
    if not (np.isfinite(min_quality) and 0.0 <= min_quality <= 1.0):
        raise ParameterError("min_quality must be between 0 and 1")


def _to8(a: FloatImage, lo: float, hi: float) -> ImageU8:
    return cast(ImageU8, np.clip((a - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8))


def extract_fingerprint(
    bgr: ImageU8,
    *,
    period: float | None = None,
    min_quality: float = 0.25,
    flip: bool = False,
    crop: bool = True,
    debug: bool = False,
) -> ExtractionResult:
    """Extract the fingerprint from a BGR uint8 photo of a finger.

    Raises ParameterError for invalid arguments and ImageTooSmallError,
    ResolutionTooLowError, WorkAreaTooLargeError or NoRidgePatternError (all
    ExtractionError) when no fingerprint can be extracted.
    """
    _check_arguments(bgr, period, min_quality)
    h, w = bgr.shape[:2]
    detected = finger_mask(bgr)
    found_finger = detected is not None
    mask: Mask = detected if detected is not None else np.ones((h, w), bool)
    gray = cast(FloatImage, bgr[:, :, 1].astype(np.float32) / 255.0)  # green shows ridges best on skin

    if period is None:
        period = estimate_period(gray, mask)
    if period < MIN_PERIOD:
        raise ResolutionTooLowError(
            f"ridges are only {period:.1f}px apart: the photo is too low-resolution "
            "(take it closer, or pass --period if the estimate is wrong)"
        )

    # Work on the finger's bounding box, rescaled so ridges are WORK_PERIOD px apart.
    bx, by, bw, bh = cv2.boundingRect(mask.astype(np.uint8))
    pad = int(3 * period)
    y0, y1 = max(by - pad, 0), min(by + bh + pad, h)
    x0, x1 = max(bx - pad, 0), min(bx + bw + pad, w)
    scale = WORK_PERIOD / period
    if (y1 - y0) * (x1 - x0) * scale * scale > MAX_WORK_PIXELS:
        raise WorkAreaTooLargeError(
            f"at a ridge spacing of {period:.1f}px the finger area is too large to process; "
            "crop the photo to the finger or check --period"
        )
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    g = cast(FloatImage, cv2.resize(gray[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=interp))
    m_resized = cv2.resize(
        mask[y0:y1, x0:x1].astype(np.float32), (g.shape[1], g.shape[0]), interpolation=cv2.INTER_LINEAR
    )
    m = cast(FloatImage, (m_resized > 0.5).astype(np.float32))
    p = WORK_PERIOD

    # 1. Flatten lighting and equalize contrast.
    hp = (g - masked_blur(g, m, 0.7 * p)) * m
    std = np.sqrt(masked_blur(hp * hp, m, 2 * p))
    norm = cast(FloatImage, hp / (std + 0.05 * float(np.median(std[m > 0])) + 1e-6) * m)

    # 2. Ridge direction + orientation-adaptive Gabor filtering, twice: the second
    #    pass takes its directions from the cleaner first-pass result.
    kernels, bank_power = gabor_bank(p)
    enh, _ = oriented_filter(norm, ridge_orientation(norm, m, p), kernels)
    phi = ridge_orientation(enh, m, 0.6 * p)
    enh, power = oriented_filter(norm, phi, kernels)

    # 3. Ridge quality and the single compact area kept as the print.
    quality = ridge_quality(enh, power, phi, m, period=p, bank_power=bank_power)
    region = print_region(quality, m, p, min_quality)

    # 4. Threshold the smooth filter output at the photo's resolution (or finer for
    #    low-res photos when cropping, so ridge edges stay smooth).
    if crop:  # just the print, plus one ridge spacing of margin
        out_scale = max(1.0, WORK_PERIOD / period)
        rx, ry, rw, rh = cv2.boundingRect((region > 0.5).astype(np.uint8))
        wx0, wy0 = max(rx - int(p), 0), max(ry - int(p), 0)
        wx1, wy1 = min(rx + rw + int(p), enh.shape[1]), min(ry + rh + int(p), enh.shape[0])
        f = out_scale / scale  # output pixels per working pixel
        size = (round((wx1 - wx0) * f), round((wy1 - wy0) * f))
    else:  # the whole finger box, pasted back into a frame the size of the photo
        out_scale = 1.0
        wx0, wy0, wx1, wy1 = 0, 0, enh.shape[1], enh.shape[0]
        size = (x1 - x0, y1 - y0)
    enh_out = cv2.resize(enh[wy0:wy1, wx0:wx1], size, interpolation=cv2.INTER_CUBIC)
    region_out = cv2.resize(region[wy0:wy1, wx0:wx1], size, interpolation=cv2.INTER_LINEAR) > 0.5
    if not region_out.any():
        raise NoRidgePatternError(NO_RIDGES)
    ridges = (enh_out < 0) if flip else (enh_out > 0)  # ridges are the bright lines in a photo
    p_out = period * out_scale
    kept = remove_specks(ridges & region_out, min_area=0.25 * p_out * p_out)
    result = kept.astype(np.uint8) * 255
    if not crop:
        full = np.zeros((h, w), np.uint8)
        full[y0:y1, x0:x1] = result
        result = full

    debug_images = None
    if debug:
        overlay = bgr[y0:y1, x0:x1].copy()
        outline = cv2.resize(region, (x1 - x0, y1 - y0)) > 0.5
        contours, _ = cv2.findContours(outline.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(overlay, contours, -1, (0, 255, 0), max(2, round(period / 4)))
        debug_images = DebugImages(
            region=overlay,
            normalized=_to8(norm, -2.5, 2.5),
            gabor=_to8(enh, -1.5, 1.5),
            quality=_to8(quality, 0, 1),
        )

    return ExtractionResult(image=result, period=period, found_finger=found_finger, debug=debug_images)
