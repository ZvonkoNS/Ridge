"""Extraction pipeline: photo of a finger in, white-on-black fingerprint out (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask
from ridge.errors import ParameterError, ResolutionTooLowError, WorkAreaTooLargeError
from ridge.pipeline.gabor import gabor_bank, oriented_filter, ridge_orientation
from ridge.pipeline.imgutil import masked_blur
from ridge.pipeline.location import PrintLocation, locate
from ridge.pipeline.mask import finger_mask
from ridge.pipeline.period import estimate_period
from ridge.pipeline.quality import print_region, ridge_quality
from ridge.pipeline.render import binarize, render_gray

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
    # Output pixels per photo pixel: max(1, WORK_PERIOD / period) when cropping, 1.0 with
    # crop=False. Nominal: rounding the output size to whole pixels changes the achieved
    # scale by less than one pixel over the image. Export scaling (500 ppi) depends on it.
    output_scale: float = 1.0
    # Where the print came from, in the pixels of the photo passed in (None only when built by hand).
    location: PrintLocation | None = None
    # The grayscale twin of `image` (PRD FR-37): the same window and size, with the filter output
    # mapped through a soft contrast curve instead of a threshold (ridge.pipeline.render). None
    # only when built by hand.
    gray: ImageU8 | None = None


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


@dataclass(frozen=True)
class _WorkArea:
    """The finger's bounding box in photo pixels, padded, and the scale that makes ridges WORK_PERIOD apart."""

    y0: int
    y1: int
    x0: int
    x1: int
    scale: float


@dataclass(frozen=True)
class _Enhanced:
    """Working-scale images: contrast-normalised photo, Gabor output, ridge quality and the print region."""

    norm: FloatImage
    enh: FloatImage
    quality: FloatImage
    region: FloatImage


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
    mask: Mask = detected if detected is not None else np.ones((h, w), bool)
    gray = cast(FloatImage, bgr[:, :, 1].astype(np.float32) / 255.0)  # green shows ridges best on skin
    if period is None:
        period = estimate_period(gray, mask)
    if period < MIN_PERIOD:
        raise ResolutionTooLowError(
            f"ridges are only {period:.1f}px apart: the photo is too low-resolution "
            "(take it closer, or pass --period if the estimate is wrong)"
        )
    area = _work_area(mask, period, h, w)
    enhanced = _enhance(*_rescale(gray, mask, area), min_quality)
    window, size, out_scale = _output_window(enhanced, area, period, crop=crop)
    result, gray_print = _render(enhanced, window, size, period * out_scale, flip=flip)
    if not crop:  # paste the finger box back into a frame the size of the photo
        result, gray_print = _framed(result, area, h, w), _framed(gray_print, area, h, w)
    location = locate(
        enhanced.region,
        window=window if crop else None,
        scale=area.scale,
        bounds=(area.x0, area.y0, area.x1, area.y1),
        size=(w, h),
        period=WORK_PERIOD,
    )
    return ExtractionResult(
        image=result,
        period=period,
        found_finger=detected is not None,
        debug=_debug_images(bgr, area, enhanced, period) if debug else None,
        output_scale=float(out_scale),
        location=location,
        gray=gray_print,
    )


def _work_area(mask: Mask, period: float, h: int, w: int) -> _WorkArea:
    """Return the finger's bounding box with three ridge spacings of margin; refuse areas over MAX_WORK_PIXELS."""
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
    return _WorkArea(y0, y1, x0, x1, scale)


def _rescale(gray: FloatImage, mask: Mask, area: _WorkArea) -> tuple[FloatImage, FloatImage]:
    """Cut the work area out of the photo and the finger mask, rescaled so ridges are WORK_PERIOD px apart."""
    interp = cv2.INTER_AREA if area.scale < 1 else cv2.INTER_CUBIC
    photo = gray[area.y0 : area.y1, area.x0 : area.x1]
    g = cast(FloatImage, cv2.resize(photo, None, fx=area.scale, fy=area.scale, interpolation=interp))
    m_resized = cv2.resize(
        mask[area.y0 : area.y1, area.x0 : area.x1].astype(np.float32),
        (g.shape[1], g.shape[0]),
        interpolation=cv2.INTER_LINEAR,
    )
    return g, cast(FloatImage, (m_resized > 0.5).astype(np.float32))


def _enhance(g: FloatImage, m: FloatImage, min_quality: float) -> _Enhanced:
    """Normalise, filter and rate the ridges at working scale; keep the single compact print region."""
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
    return _Enhanced(norm, enh, quality, print_region(quality, m, p, min_quality))


def _output_window(
    enhanced: _Enhanced, area: _WorkArea, period: float, *, crop: bool
) -> tuple[tuple[int, int, int, int], tuple[int, int], float]:
    """Working-scale window (x0, y0, x1, y1) to output, the output size and output pixels per photo pixel.

    The smooth filter output is thresholded at the photo's resolution, or finer for low-res photos
    when cropping, so ridge edges stay smooth.
    """
    enh, p = enhanced.enh, WORK_PERIOD
    if crop:  # just the print, plus one ridge spacing of margin
        out_scale = max(1.0, WORK_PERIOD / period)
        rx, ry, rw, rh = cv2.boundingRect((enhanced.region > 0.5).astype(np.uint8))
        wx0, wy0 = max(rx - int(p), 0), max(ry - int(p), 0)
        wx1, wy1 = min(rx + rw + int(p), enh.shape[1]), min(ry + rh + int(p), enh.shape[0])
        f = out_scale / area.scale  # output pixels per working pixel
        return (wx0, wy0, wx1, wy1), (round((wx1 - wx0) * f), round((wy1 - wy0) * f)), out_scale
    # the whole finger box, at the photo's resolution
    return (0, 0, enh.shape[1], enh.shape[0]), (area.x1 - area.x0, area.y1 - area.y0), 1.0


def _render(
    enhanced: _Enhanced,
    window: tuple[int, int, int, int],
    size: tuple[int, int],
    p_out: float,
    *,
    flip: bool,
) -> tuple[ImageU8, ImageU8]:
    """Resize the filter output and the print region to output size; return the print and its grayscale twin.

    `p_out` is the output ridge spacing. Both renderings come from the same two arrays
    (ridge.pipeline.render), so the grayscale print shows nothing beyond the print's region.
    """
    wx0, wy0, wx1, wy1 = window
    enh_out = cast(FloatImage, cv2.resize(enhanced.enh[wy0:wy1, wx0:wx1], size, interpolation=cv2.INTER_CUBIC))
    region_out = cast(FloatImage, cv2.resize(enhanced.region[wy0:wy1, wx0:wx1], size, interpolation=cv2.INTER_LINEAR))
    return binarize(enh_out, region_out, p_out, flip=flip), render_gray(enh_out, region_out, flip=flip)


def _framed(image: ImageU8, area: _WorkArea, h: int, w: int) -> ImageU8:
    """Paste an output of the finger box back into a black frame the size of the photo (crop=False)."""
    full = np.zeros((h, w), np.uint8)
    full[area.y0 : area.y1, area.x0 : area.x1] = image
    return cast(ImageU8, full)


def _debug_images(bgr: ImageU8, area: _WorkArea, enhanced: _Enhanced, period: float) -> DebugImages:
    """Return what the pipeline saw at each step, for review (written only on request: class E data)."""
    overlay = bgr[area.y0 : area.y1, area.x0 : area.x1].copy()
    size = (area.x1 - area.x0, area.y1 - area.y0)
    outline = cv2.resize(enhanced.region, size, interpolation=cv2.INTER_LINEAR) > 0.5
    contours, _ = cv2.findContours(outline.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(overlay, contours, -1, (0, 255, 0), max(2, round(period / 4)))
    return DebugImages(
        region=overlay,
        normalized=_to8(enhanced.norm, -2.5, 2.5),
        gabor=_to8(enhanced.enh, -1.5, 1.5),
        quality=_to8(enhanced.quality, 0, 1),
    )
