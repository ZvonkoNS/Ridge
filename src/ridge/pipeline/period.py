"""Ridge-spacing measurement with local Fourier analysis."""

from __future__ import annotations

import math
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from ridge.arrays import FloatImage, Mask
from ridge.errors import ImageTooSmallError

PATCH = 96  # patch size in pixels after rescaling
STEP = 24  # patch stride
NFFT = 256  # zero-padded FFT size
FINGER_WIDTH_PX = 640.0  # finger width the photo is rescaled to before measuring
MAX_MEASURE_PIXELS = 16_000_000  # memory bound on the rescaled image (CWE-789)
MIN_FINGER_WIDTH_PX = 75.0  # ~25 ridges at the smallest resolvable spacing (3 px)
FINGER_TOO_SMALL = (
    "the finger is too small in the photo to measure the ridge spacing (take it closer, or pass --period)"
)


def measure_scale(height: int, width: int, finger_width: float) -> float:
    """Factor that rescales the photo so the finger is ~FINGER_WIDTH_PX wide, within the memory bound."""
    if finger_width < MIN_FINGER_WIDTH_PX:
        raise ImageTooSmallError(FINGER_TOO_SMALL)
    return min(FINGER_WIDTH_PX / finger_width, math.sqrt(MAX_MEASURE_PIXELS / (height * width)))


def _patch_origins(height: int, width: int) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    ys, xs = np.mgrid[0 : height - PATCH + 1 : STEP, 0 : width - PATCH + 1 : STEP]
    return ys.ravel(), xs.ravel()


def estimate_period(gray: FloatImage, mask: Mask) -> float:
    """Dominant ridge spacing in pixels, from the spectra of small patches on the finger."""
    # Rescale so the finger is ~640 px wide; a finger is roughly 25-60 ridges wide,
    # so one patch size and one search band then fit photos of any resolution.
    dist = cv2.distanceTransform(np.pad(mask, 1).astype(np.uint8), cv2.DIST_L2, 5)
    s = measure_scale(gray.shape[0], gray.shape[1], 2.0 * float(dist.max()))
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    g = cast(FloatImage, cv2.resize(gray, None, fx=s, fy=s, interpolation=interp))
    m = cv2.resize(mask.astype(np.uint8), (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST)
    g = g - cv2.GaussianBlur(g, (0, 0), 6)  # drop lighting gradients

    win = np.outer(np.hanning(PATCH), np.hanning(PATCH)).astype(np.float32)
    fy = np.fft.fftfreq(NFFT)[:, None]
    fx = np.fft.rfftfreq(NFFT)[None, :]
    radius = np.hypot(fx, fy)
    band = (radius > 1 / 40) & (radius < 1 / 3.5)  # ~16..180 ridges across the finger
    band_radius = radius[band]
    whiten = band_radius**2  # flattens the 1/f^2 falloff of natural images

    coverage = cv2.boxFilter(m.astype(np.float32), -1, (PATCH, PATCH), anchor=(0, 0), normalize=True)
    ys, xs = _patch_origins(g.shape[0], g.shape[1])
    inside = coverage[ys, xs] > 0.95
    ys, xs = ys[inside], xs[inside]
    if len(ys) < 4:  # finger too small for patches: fall back to the whole frame
        ys, xs = _patch_origins(g.shape[0], g.shape[1])
    if len(ys) == 0:
        raise ImageTooSmallError("image too small to measure ridge spacing; pass --period")

    raw_chunks, period_chunks, sharp_chunks = [], [], []
    for i in range(0, len(ys), 256):
        patches = np.stack(
            [g[y : y + PATCH, x : x + PATCH] for y, x in zip(ys[i : i + 256], xs[i : i + 256], strict=True)]
        )
        patches = (patches - patches.mean(axis=(1, 2), keepdims=True)) * win
        power = (np.abs(np.fft.rfft2(patches, s=(NFFT, NFFT))) ** 2)[:, band]
        raw_chunks.append(1.0 / band_radius[np.argmax(power, axis=1)])
        power *= whiten
        peak = np.argmax(power, axis=1)
        period_chunks.append(1.0 / band_radius[peak])
        # Share of in-band energy at the peak: high for a clean ridge wave, tiny for noise.
        sharp_chunks.append(power[np.arange(len(peak)), peak] / (power.sum(axis=1) + 1e-12))
    raw_periods = np.concatenate(raw_chunks)
    periods = np.concatenate(period_chunks)
    sharpness = np.concatenate(sharp_chunks)

    # A real ridge wave is the peak with and without whitening; shading only wins the
    # raw spectrum and noise only the whitened one. Then trust the sharpest quarter.
    good = np.abs(np.log(raw_periods / periods)) < 0.12
    if good.sum() < 4:
        good[:] = True
    p, wt = periods[good], sharpness[good]
    best = wt >= np.quantile(wt, 0.75)
    p, wt = p[best], wt[best]
    order = np.argsort(p)
    cum = np.cumsum(wt[order])
    period = p[order][np.searchsorted(cum, cum[-1] / 2)]
    return float(period) / s
