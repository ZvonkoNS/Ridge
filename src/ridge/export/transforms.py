"""Comparison-export transforms: polarity, mirror and 500 ppi scaling (pure, no I/O).

Ridge extracts white ridges on black at the photo's (cropped) resolution. Comparison against
contact impressions and NAFIS/AFIS results needs their conventions instead (PRD FR-30, FR-31):

* polarity: dark ridges on a light background;
* orientation: a photo shows the finger pad as seen, a contact impression is its mirror
  image, so the export is flipped left to right;
* resolution: 500 pixels per inch. A photo has no calibrated resolution, so the scale is an
  estimate (``ScaleEstimate``) whose method and uncertainty must be reported with the export.

``make_comparison_export`` applies all three and lists them in ``ExportResult.transforms`` so
the job report can record exactly what was done (FR-34). The result is a processed image for
an examiner to compare; it is not an identification and makes no conclusion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal, cast

import cv2
import numpy as np

from ridge.arrays import ImageU8
from ridge.errors import ExportTooLargeError, ParameterError
from ridge.export.validate import finite, gray_u8, positive, ppi_value
from ridge.pipeline.extract import ExtractionResult

type ScaleMethod = Literal["ruler", "ridge-period", "manual"]
SCALE_METHODS: Final[tuple[ScaleMethod, ...]] = ("ruler", "ridge-period", "manual")
type Tone = Literal["binary", "grayscale"]  # which print an export is made from (FR-30, FR-37)
TONES: Final[tuple[Tone, ...]] = ("binary", "grayscale")

MM_PER_INCH: Final = 25.4
DEFAULT_PPI: Final = 500.0  # usual AFIS resolution, and the one NFIQ 2 is defined for
MAX_EXPORT_PIXELS: Final = 50_000_000  # bound on the resampled export (CWE-789)

# Ridge-period method (FR-31 b). ENGINEERING ASSUMPTIONS, not measurements: the mean adult
# ridge-to-ridge distance is taken as about 0.47 mm, close to the ~9 px ridge period typical of
# 500 ppi contact prints (9 px = 0.457 mm). It varies considerably between people (sex, age,
# finger) and within one print, so +-15 % is a placeholder. Both values must be confirmed or
# replaced by the validation study (PRD section 12) before casework use; a ruler in the photo
# is preferred whenever one is available.
ASSUMED_RIDGE_PERIOD_MM: Final = 0.47
RIDGE_PERIOD_UNCERTAINTY_PCT: Final = 15.0
CLICK_ERROR_PX: Final = 1.0  # assumed error of each ruler point placed by the examiner

TONE_GRAYSCALE: Final = "tone:grayscale"  # first transform of a grayscale export
POLARITY_DARK_RIDGES: Final = "polarity:dark-ridges"
MIRROR_HORIZONTAL: Final = "mirror:horizontal"


@dataclass(frozen=True, slots=True)
class ScaleEstimate:
    """Physical scale of the photo: how many photo pixels make one millimetre on the finger.

    ``px_per_mm`` refers to the decoded photo (after EXIF orientation), not to the extraction
    output. ``uncertainty_pct`` is the approximate relative uncertainty of ``px_per_mm`` in
    percent: a worst-case bound for the ruler, an assumption for the ridge-period method and
    the examiner's statement for "manual". It is not a statistical confidence interval.
    """

    px_per_mm: float
    method: ScaleMethod
    uncertainty_pct: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "px_per_mm", positive(self.px_per_mm, "px_per_mm"))
        if self.method not in SCALE_METHODS:
            raise ParameterError(f"scale method must be one of {', '.join(SCALE_METHODS)}")
        uncertainty = finite(self.uncertainty_pct, "uncertainty_pct")
        if uncertainty < 0:
            raise ParameterError("uncertainty_pct must not be negative")
        object.__setattr__(self, "uncertainty_pct", uncertainty)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """A comparison image ready for encoding, with everything the job report must record.

    ``image`` is H x W uint8, dark ridges on light, at ``ppi`` pixels per inch (nominal: the
    size is rounded to whole pixels). ``factor`` is the resampling factor applied to the
    extraction output (export pixels per extraction-output pixel). ``transforms`` lists the
    applied steps in order, e.g. ``("polarity:dark-ridges", "mirror:horizontal",
    "scale:500ppi:ruler")``; a grayscale export starts with ``"tone:grayscale"``.
    """

    image: ImageU8
    ppi: float
    scale: ScaleEstimate
    factor: float
    transforms: tuple[str, ...]


def to_comparison(image: ImageU8) -> ImageU8:
    """Invert white ridges on black (0/255) into dark ridges on a light background (FR-30).

    Exact and lossless for any H x W uint8 image: each value v becomes 255 - v.
    """
    return cast(ImageU8, np.subtract(np.uint8(255), gray_u8(image), dtype=np.uint8))


def mirror(image: ImageU8) -> ImageU8:
    """Flip an H x W uint8 image left to right (photo of the pad -> contact orientation, FR-30).

    Returns a new contiguous array; the input is not modified.
    """
    return cast(ImageU8, np.ascontiguousarray(gray_u8(image)[:, ::-1]))


def _point(p: object, name: str) -> tuple[float, float]:
    if not (isinstance(p, tuple | list) and len(p) == 2):
        raise ParameterError(f"{name} must be an (x, y) pair of pixel coordinates")
    return finite(p[0], f"{name} x"), finite(p[1], f"{name} y")


def scale_from_ruler(p1: tuple[float, float], p2: tuple[float, float], distance_mm: float) -> ScaleEstimate:
    """Scale from two points a known distance apart on a ruler in the photo (FR-31 a).

    `p1` and `p2` are (x, y) positions in photo pixels (after EXIF orientation); `distance_mm`
    is the true distance between them. Each point is assumed to be off by up to
    CLICK_ERROR_PX along the ruler, so ``uncertainty_pct = 100 * 2 / pixel distance``: measure
    over a long stretch of the ruler. Perspective, lens distortion and a ruler lying in a
    different plane from the finger are not covered and belong to method validation.
    """
    x1, y1 = _point(p1, "p1")
    x2, y2 = _point(p2, "p2")
    mm = positive(distance_mm, "distance_mm")
    pixels = math.hypot(x2 - x1, y2 - y1)
    if pixels == 0:
        raise ParameterError("p1 and p2 must be different points")
    return ScaleEstimate(px_per_mm=pixels / mm, method="ruler", uncertainty_pct=100.0 * 2 * CLICK_ERROR_PX / pixels)


def scale_from_ridge_period(
    period_px: float,
    assumed_period_mm: float = ASSUMED_RIDGE_PERIOD_MM,
    uncertainty_pct: float = RIDGE_PERIOD_UNCERTAINTY_PCT,
) -> ScaleEstimate:
    """Scale from the measured ridge period and an assumed ridge distance (FR-31 b, fallback).

    `period_px` is the ridge spacing in photo pixels (``ExtractionResult.period``). The
    defaults are engineering assumptions to be validated (see ASSUMED_RIDGE_PERIOD_MM); the
    result is an assumption-based estimate, not a measurement of this finger.
    """
    period = positive(period_px, "period_px")
    mm = positive(assumed_period_mm, "assumed_period_mm")
    return ScaleEstimate(px_per_mm=period / mm, method="ridge-period", uncertainty_pct=uncertainty_pct)


def _scale(photo_scale: object) -> ScaleEstimate:
    if not isinstance(photo_scale, ScaleEstimate):
        raise ParameterError("photo_scale must be a ScaleEstimate")
    return photo_scale


def to_ppi(
    image: ImageU8, *, photo_scale: ScaleEstimate, output_scale: float, target_ppi: float = DEFAULT_PPI
) -> tuple[ImageU8, float]:
    """Resample an H x W uint8 image to `target_ppi` pixels per inch; return (image, factor).

    The image has `output_scale` pixels per photo pixel (``ExtractionResult.output_scale``),
    so it holds ``photo_scale.px_per_mm * output_scale`` pixels per millimetre, and
    ``factor = (target_ppi / 25.4) / that``. The new size is rounded to whole pixels (the
    achieved scale differs from `factor` by under half a pixel across the image). Downscaling
    averages areas (anti-aliasing), upscaling is bicubic; values are computed in float32,
    clipped and rounded, so a binary input becomes anti-aliased grayscale, which suits
    comparison images. Raises ParameterError for invalid arguments and ExportTooLargeError
    when the result would exceed MAX_EXPORT_PIXELS (CWE-789; usually a wrong scale).
    """
    src = gray_u8(image)
    target = ppi_value(target_ppi, "target_ppi")
    image_px_per_mm = _scale(photo_scale).px_per_mm * positive(output_scale, "output_scale")
    if not (math.isfinite(image_px_per_mm) and image_px_per_mm > 0):
        raise ParameterError("photo_scale and output_scale give an unusable image scale")
    factor = (target / MM_PER_INCH) / image_px_per_mm
    height, width = src.shape
    limit = f"the limit is {MAX_EXPORT_PIXELS / 1e6:.0f} MP; check the scale"
    if not (width * factor <= MAX_EXPORT_PIXELS and height * factor <= MAX_EXPORT_PIXELS):
        raise ExportTooLargeError(f"at {target:g} ppi the export would be enlarged {factor:.3g} times; {limit}")
    size = (round(width * factor), round(height * factor))
    if size[0] * size[1] > MAX_EXPORT_PIXELS:
        raise ExportTooLargeError(f"at {target:g} ppi the export would be {size[0]}x{size[1]} px; {limit}")
    if min(size) < 1:
        raise ParameterError(f"at {target:g} ppi the export would be smaller than one pixel; check the scale")
    interpolation = cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(src.astype(np.float32), size, interpolation=interpolation)
    return cast(ImageU8, np.clip(np.rint(resized), 0, 255).astype(np.uint8)), factor


def _source(result: ExtractionResult, tone: object) -> tuple[ImageU8, list[str]]:
    """Return the print an export starts from and the transform names that say so."""
    if tone == "binary":
        return result.image, []
    if tone == "grayscale":
        if result.gray is None:
            raise ParameterError("this extraction result has no grayscale print to export")
        return result.gray, [TONE_GRAYSCALE]
    raise ParameterError(f"tone must be one of {', '.join(TONES)}")


def make_comparison_export(
    result: ExtractionResult,
    photo_scale: ScaleEstimate,
    *,
    mirror_image: bool = True,
    target_ppi: float = DEFAULT_PPI,
    tone: Tone = "binary",
) -> ExportResult:
    """Turn an extraction result into a comparison export: polarity, mirror, then scale.

    `tone` chooses the source: ``"binary"`` is the print (``result.image``, FR-30 to FR-32),
    ``"grayscale"`` its un-thresholded twin (``result.gray``, FR-37), whose transforms start with
    ``"tone:grayscale"``. Both get the same geometry, so they overlay exactly.
    `mirror_image=False` skips the left-right flip (for example when the photo already shows
    a mirrored impression); the transforms list then omits it. The export is a processed
    image derived from the photo, for examiner comparison only.
    """
    source, steps = _source(result, tone)
    image = to_comparison(source)
    steps.append(POLARITY_DARK_RIDGES)
    if mirror_image:
        image = mirror(image)
        steps.append(MIRROR_HORIZONTAL)
    scaled, factor = to_ppi(image, photo_scale=photo_scale, output_scale=result.output_scale, target_ppi=target_ppi)
    target = float(target_ppi)
    steps.append(f"scale:{target:g}ppi:{photo_scale.method}")
    return ExportResult(image=scaled, ppi=target, scale=photo_scale, factor=factor, transforms=tuple(steps))
