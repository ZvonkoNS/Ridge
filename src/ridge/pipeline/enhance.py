"""Ridge enhancement at working scale: contrast normalisation, Gabor filtering, ridge quality, print region.

Pure functions shared by the characterised pipeline (one Gabor bank at WORK_PERIOD) and the opt-in
local-frequency variant (ADR-014, `ridge.pipeline.frequency`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np

from ridge.arrays import FloatImage
from ridge.pipeline.frequency import band_filter, banks, local_period_map
from ridge.pipeline.gabor import gabor_bank, oriented_filter, ridge_orientation
from ridge.pipeline.imgutil import masked_blur
from ridge.pipeline.quality import print_region, ridge_quality

WORK_PERIOD = 12.0  # ridge spacing in pixels that the photo is rescaled to for filtering


@dataclass(frozen=True)
class Enhanced:
    """Working-scale images: contrast-normalised photo, Gabor output, ridge quality and the print region."""

    norm: FloatImage
    enh: FloatImage
    quality: FloatImage
    region: FloatImage
    spacing: FloatImage | None = None  # the local ridge spacing used, when the local-frequency variant was on


def enhance(g: FloatImage, m: FloatImage, min_quality: float, *, local: bool = False) -> Enhanced:
    """Normalise, filter and rate the ridges at working scale; keep the single compact print region.

    With `local` (ADR-014 variant) each pixel is filtered with the bank tuned to its own measured
    spacing and periodicity is checked at that spacing; otherwise one bank at WORK_PERIOD, as v0.
    """
    p = WORK_PERIOD
    # 1. Flatten lighting and equalize contrast.
    hp = (g - masked_blur(g, m, 0.7 * p)) * m
    std = np.sqrt(masked_blur(hp * hp, m, 2 * p))
    norm = cast(FloatImage, hp / (std + 0.05 * float(np.median(std[m > 0])) + 1e-6) * m)
    if local:
        return _enhance_local(norm, m, p, min_quality)

    # 2. Ridge direction + orientation-adaptive Gabor filtering, twice: the second
    #    pass takes its directions from the cleaner first-pass result.
    kernels, bank_power = gabor_bank(p)
    enh, _ = oriented_filter(norm, ridge_orientation(norm, m, p), kernels)
    phi = ridge_orientation(enh, m, 0.6 * p)
    enh, power = oriented_filter(norm, phi, kernels)

    # 3. Ridge quality and the single compact area kept as the print.
    quality = ridge_quality(enh, power, phi, m, period=p, bank_power=bank_power)
    return Enhanced(norm, enh, quality, print_region(quality, m, p, min_quality))


def _enhance_local(norm: FloatImage, m: FloatImage, p: float, min_quality: float) -> Enhanced:
    """Run steps 2 and 3 with a local spacing map and a multi-frequency bank (ridge.pipeline.frequency)."""
    spacing = local_period_map(norm, m, p)
    bank_set = banks(p)
    enh, _, _ = band_filter(norm, ridge_orientation(norm, m, p), spacing, bank_set)
    phi = ridge_orientation(enh, m, 0.6 * p)
    enh, power, bank_power = band_filter(norm, phi, spacing, bank_set)
    quality = ridge_quality(enh, power, phi, m, period=p, bank_power=bank_power, spacing=spacing)
    return Enhanced(norm, enh, quality, print_region(quality, m, p, min_quality), spacing)


def spacing_range(enhanced: Enhanced, scale: float) -> tuple[float, float, float] | None:
    """(min, median, max) of the local spacing inside the print region, in photo pixels; None without the variant."""
    if enhanced.spacing is None:
        return None
    inside = enhanced.spacing[enhanced.region > 0.5]
    values = inside if inside.size else enhanced.spacing.ravel()
    return float(values.min() / scale), float(np.median(values) / scale), float(values.max() / scale)
