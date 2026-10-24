"""Local ridge frequency and a multi-frequency Gabor bank (ADR-014 variant ``local_frequency``; pure).

One global ridge spacing fits a flat, evenly spaced print. On a photographed finger the spacing
varies: finer towards the core, coarser towards the edges, and perspective compresses the sides of
the curved pad. Where the local spacing drifts far from the global value, the bank tuned to the
global value answers weakly and the periodicity check, which looks one nominal spacing ahead and
behind, fails, so the quality gate drops the area. This variant measures the spacing in blocks at
working scale (the same patch-spectrum method as `ridge.pipeline.period`), fills the blocks it
cannot trust from their measured neighbours, smooths and clamps the map, filters each pixel with
the bank tuned to its own spacing by interpolating between the two nearest banks of a small set
(Hong, Wan and Jain 1998 use a frequency image the same way), and checks periodicity at the local
spacing. The nominal spacing stays WORK_PERIOD. Unvalidated, off by default, recorded in the
report as the range of spacings used.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast

import cv2
import numpy as np

from ridge.arrays import FloatImage
from ridge.pipeline.gabor import gabor_bank, oriented_filter

BANDS: Final = (0.70, 0.84, 1.0, 1.19, 1.42, 1.68)  # bank spacings relative to the nominal, geometric steps of ~1.19
MIN_RATIO: Final = BANDS[0]
MAX_RATIO: Final = BANDS[-1]
BLOCK: Final = 64  # block side at working scale: about five ridges
STEP: Final = 16
NFFT: Final = 256
COVERAGE: Final = 0.9  # a block must lie this far inside the finger to be measured
RELIABLE_FRACTION: Final = 0.5  # a block whose spectral peak share is below this fraction of the median is not trusted
FILL_SIGMA: Final = 2.0  # cells: reach of the measured neighbours that fill an untrusted block
FILL_MIN_WEIGHT: Final = 0.05  # less measured weight nearby than this: the nominal spacing instead

type Bank = tuple[list[FloatImage], float, float]  # kernels, bank power, spacing in pixels


def banks(nominal: float) -> list[Bank]:
    """One Gabor bank per band spacing around `nominal`."""
    return [(*gabor_bank(ratio * nominal), ratio * nominal) for ratio in BANDS]


def _block_periods(norm: FloatImage, ys: np.ndarray, xs: np.ndarray, nominal: float) -> tuple[np.ndarray, np.ndarray]:
    """Measure the ridge spacing and the spectral peak share of each block at (ys, xs)."""
    win = np.outer(np.hanning(BLOCK), np.hanning(BLOCK)).astype(np.float32)
    fy = np.fft.fftfreq(NFFT)[:, None]
    fx = np.fft.rfftfreq(NFFT)[None, :]
    radius = np.hypot(fx, fy)
    band = (radius > 1.0 / (MAX_RATIO * nominal)) & (radius < 1.0 / (MIN_RATIO * nominal))
    band_radius = radius[band]
    whiten = band_radius**2  # flattens the 1/f^2 falloff of natural images, as the global estimate does
    periods = np.full(len(ys), nominal, np.float32)
    sharpness = np.zeros(len(ys), np.float32)
    for i in range(0, len(ys), 256):
        rows, cols = ys[i : i + 256], xs[i : i + 256]
        patches = np.stack([norm[y : y + BLOCK, x : x + BLOCK] for y, x in zip(rows, cols, strict=True)])
        patches = (patches - patches.mean(axis=(1, 2), keepdims=True)) * win
        power = (np.abs(np.fft.rfft2(patches, s=(NFFT, NFFT))) ** 2)[:, band] * whiten
        peak = np.argmax(power, axis=1)
        periods[i : i + 256] = 1.0 / band_radius[peak]
        sharpness[i : i + 256] = power[np.arange(len(peak)), peak] / (power.sum(axis=1) + 1e-12)
    return periods, sharpness


def _fill_grid(values: FloatImage, measured: np.ndarray, nominal: float) -> FloatImage:
    """Fill the untrusted cells of the block grid from their measured neighbours; the nominal where none is near."""
    weight = measured.astype(np.float32)
    near_weight = cv2.GaussianBlur(weight, (0, 0), FILL_SIGMA, borderType=cv2.BORDER_CONSTANT)
    near_values = cv2.GaussianBlur(values * weight, (0, 0), FILL_SIGMA, borderType=cv2.BORDER_CONSTANT)
    filled = np.where(near_weight > FILL_MIN_WEIGHT, near_values / np.maximum(near_weight, 1e-6), np.float32(nominal))
    return cast(FloatImage, np.where(measured, values, filled).astype(np.float32))


def _upsample(grid: FloatImage, shape: tuple[int, int]) -> FloatImage:
    """Spread the block grid over the image: cell (i, j) at the centre of block (i*STEP, j*STEP), linear in between."""
    h, w = shape
    gh, gw = grid.shape
    rows = np.linspace(0.0, gh - 1.0, (gh - 1) * STEP + 1, dtype=np.float32)
    cols = np.linspace(0.0, gw - 1.0, (gw - 1) * STEP + 1, dtype=np.float32)
    r0 = np.floor(rows).astype(np.intp)
    c0 = np.floor(cols).astype(np.intp)
    fr, fc = (rows - r0)[:, None], (cols - c0)[None, :]
    by_row = grid[r0] * (1 - fr) + grid[np.minimum(r0 + 1, gh - 1)] * fr
    inner = by_row[:, c0] * (1 - fc) + by_row[:, np.minimum(c0 + 1, gw - 1)] * fc
    margin = BLOCK // 2
    pad = ((margin, h - margin - inner.shape[0]), (margin, w - margin - inner.shape[1]))
    return cast(FloatImage, np.pad(inner, pad, mode="edge").astype(np.float32))


def local_period_map(norm: FloatImage, mask: FloatImage, nominal: float) -> FloatImage:
    """Return the local ridge spacing (pixels) at every pixel of a working-scale image, clamped to the band range.

    `norm` is the contrast-normalised image, `mask` the finger (0..1). Blocks reaching outside the
    finger are not measured and blocks much blurrier than the typical block are not trusted; both are
    filled from their measured neighbours. The block grid is median-filtered, smoothed, clamped and
    spread over the image. An image smaller than a block is given the nominal spacing throughout.
    """
    h, w = norm.shape
    nominal_map = np.full((h, w), np.float32(nominal), np.float32)
    if h < BLOCK or w < BLOCK:
        return nominal_map
    gy, gx = np.mgrid[0 : h - BLOCK + 1 : STEP, 0 : w - BLOCK + 1 : STEP]
    ys, xs = gy.ravel(), gx.ravel()
    coverage = cv2.boxFilter(mask, -1, (BLOCK, BLOCK), anchor=(0, 0), normalize=True)
    inside = np.flatnonzero(coverage[ys, xs] > COVERAGE)
    if inside.size == 0:
        return nominal_map
    block_periods, sharpness = _block_periods(norm, ys[inside], xs[inside], nominal)
    reliable = sharpness >= RELIABLE_FRACTION * float(np.median(sharpness))
    values, measured = np.zeros(len(ys), np.float32), np.zeros(len(ys), bool)
    values[inside[reliable]], measured[inside[reliable]] = block_periods[reliable], True
    grid = _fill_grid(cast(FloatImage, values.reshape(gy.shape)), measured.reshape(gy.shape), nominal)
    if min(grid.shape) >= 3:
        grid = np.asarray(cv2.medianBlur(grid, 3), dtype=np.float32)
    grid = np.asarray(cv2.GaussianBlur(grid, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT), dtype=np.float32)
    return _upsample(np.clip(grid, MIN_RATIO * nominal, MAX_RATIO * nominal).astype(np.float32), (h, w))


def band_filter(
    img: FloatImage, phi: FloatImage, spacing: FloatImage, bank_set: Sequence[Bank]
) -> tuple[FloatImage, FloatImage, FloatImage]:
    """Filter each pixel with the bank tuned to its spacing, interpolating between the two nearest bands.

    Returns the filtered image, the summed power of all orientations and the bank power at each pixel,
    the three inputs `ridge.pipeline.quality.ridge_quality` needs.
    """
    periods = np.array([spacing_px for _, _, spacing_px in bank_set], dtype=np.float64)
    pos = np.interp(np.log(spacing.astype(np.float64)), np.log(periods), np.arange(len(bank_set))).astype(np.float32)
    k0 = np.clip(np.floor(pos), 0, len(bank_set) - 2).astype(np.int32)
    w1 = (pos - k0).astype(np.float32)
    k1 = k0 + 1
    out, power, bank_power = np.zeros_like(img), np.zeros_like(img), np.zeros_like(img)
    for k, (kernels, gain, _) in enumerate(bank_set):
        weight = np.where(k0 == k, 1 - w1, np.float32(0)) + np.where(k1 == k, w1, np.float32(0))
        if not weight.any():
            continue  # no pixel asks for this band: skip its 16 filters
        enh_k, power_k = oriented_filter(img, phi, kernels)
        out += weight * enh_k
        power += weight * power_k
        bank_power += weight * np.float32(gain)
    return out, power, bank_power
