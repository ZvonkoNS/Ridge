"""Extraction pipeline: photo of a finger in, white-on-black fingerprint out (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage, ImageU8, Mask
from ridge.errors import ParameterError, ResolutionTooLowError, WorkAreaTooLargeError
from ridge.pipeline.channel import gray_channel
from ridge.pipeline.enhance import WORK_PERIOD, Enhanced, enhance, spacing_range
from ridge.pipeline.location import PrintLocation, locate
from ridge.pipeline.mask import finger_mask, without_specular
from ridge.pipeline.options import MethodOptions
from ridge.pipeline.period import estimate_period
from ridge.pipeline.render import binarize, render_gray
from ridge.pipeline.upright import Rotation, rotate_bgr, rotate_mask, upright_rotation

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
    # Method variants that were on (ADR-014) and what they did; defaults for a hand-built result.
    options: MethodOptions = field(default_factory=MethodOptions)
    channel_used: str = "green"
    specular_fraction: float | None = None  # share of the finger area removed as highlights, when the mask was on
    rotation_deg: float | None = None  # rotation applied to put the finger upright, when that variant was on
    # (min, median, max) ridge spacing in photo pixels used inside the print, when the local-frequency variant was on
    local_period_px: tuple[float, float, float] | None = None


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


def _check_resolution(period: float) -> None:
    if period < MIN_PERIOD:
        raise ResolutionTooLowError(
            f"ridges are only {period:.1f}px apart: the photo is too low-resolution "
            "(take it closer, or pass --period if the estimate is wrong)"
        )


def extract_fingerprint(
    bgr: ImageU8,
    *,
    period: float | None = None,
    min_quality: float = 0.25,
    flip: bool = False,
    crop: bool = True,
    debug: bool = False,
    options: MethodOptions | None = None,
) -> ExtractionResult:
    """Extract the fingerprint from a BGR uint8 photo of a finger.

    `options` turns on method variants (ADR-014); None or the defaults give the characterised
    pipeline. Raises ParameterError for invalid arguments and ImageTooSmallError,
    ResolutionTooLowError, WorkAreaTooLargeError or NoRidgePatternError (all
    ExtractionError) when no fingerprint can be extracted.
    """
    _check_arguments(bgr, period, min_quality)
    options = options or MethodOptions()
    if not isinstance(options, MethodOptions):
        raise ParameterError("options must be a MethodOptions")
    h, w = bgr.shape[:2]
    photo_size = (w, h)
    detected = finger_mask(bgr)
    mask: Mask = detected if detected is not None else np.ones((h, w), bool)
    rotation: Rotation | None = upright_rotation(mask) if options.upright and detected is not None else None
    if rotation is not None:  # the pipeline then runs on the upright canvas; the location is mapped back below
        bgr, mask = rotate_bgr(bgr, rotation), rotate_mask(mask, rotation)
        h, w = bgr.shape[:2]
    gray, channel_used = gray_channel(bgr, options.channel, mask)  # the default is the green plane
    measured = estimate_period(gray, mask) if period is None else period
    _check_resolution(measured)
    specular_fraction: float | None = None
    if options.specular_mask:
        mask, specular_fraction = without_specular(bgr, mask, measured)
        if period is None:  # measure again without the highlights
            measured = estimate_period(gray, mask)
            _check_resolution(measured)
    period = measured
    area = _work_area(mask, period, h, w)
    enhanced = enhance(*_rescale(gray, mask, area), min_quality, local=options.local_frequency)
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
    if rotation is not None:
        location = location.in_photo(rotation, photo_size)
    return ExtractionResult(
        image=result,
        period=period,
        found_finger=detected is not None,
        debug=_debug_images(bgr, area, enhanced, period) if debug else None,
        output_scale=float(out_scale),
        location=location,
        gray=gray_print,
        options=options,
        channel_used=channel_used,
        specular_fraction=specular_fraction,
        rotation_deg=None if rotation is None else rotation.angle_deg,
        local_period_px=spacing_range(enhanced, area.scale),
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


def _output_window(
    enhanced: Enhanced, area: _WorkArea, period: float, *, crop: bool
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
    enhanced: Enhanced,
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


def _debug_images(bgr: ImageU8, area: _WorkArea, enhanced: Enhanced, period: float) -> DebugImages:
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
