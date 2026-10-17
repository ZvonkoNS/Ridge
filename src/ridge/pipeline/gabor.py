"""Ridge orientation and the orientation-adaptive Gabor filter bank (Hong, Wan & Jain, 1998)."""

from __future__ import annotations

import math
from typing import cast

import cv2
import numpy as np

from ridge.arrays import FloatImage
from ridge.pipeline.imgutil import masked_blur

N_ORIENT = 16  # orientations in the Gabor filter bank


def gabor_bank(period: float, n: int = N_ORIENT) -> tuple[list[FloatImage], float]:
    """Even-symmetric Gabor kernels tuned to `period`, for n directions across the ridges.

    Also returns the total power the whole bank passes for a clean ridge wave, which
    turns the bank into a ridge-quality detector (see oriented_filter).
    """
    sx, sy = 0.45 * period, 0.65 * period  # envelope across / along the ridges
    half = math.ceil(3 * max(sx, sy))
    y, x = np.mgrid[-half : half + 1, -half : half + 1].astype(np.float64)
    kernels: list[FloatImage] = []
    for k in range(n):
        phi = k * math.pi / n
        xr = x * math.cos(phi) + y * math.sin(phi)
        yr = -x * math.sin(phi) + y * math.cos(phi)
        env = np.exp(-0.5 * ((xr / sx) ** 2 + (yr / sy) ** 2))
        carrier = np.cos(2 * math.pi * xr / period)
        kern = env * carrier
        kern -= env * (kern.sum() / env.sum())  # zero DC: flat areas give 0
        kern /= (kern * carrier).sum()  # unit gain for a matching ridge wave
        kernels.append(kern.astype(np.float32))
    wave = np.cos(2 * math.pi * x / period)  # ridge wave aligned with kernel 0
    bank_power = sum(float((kern * wave).sum()) ** 2 for kern in kernels)
    return kernels, bank_power


def ridge_orientation(img: FloatImage, mask: FloatImage, sigma: float) -> FloatImage:
    """Direction across the ridges (radians, 0..pi) from the smoothed structure tensor."""
    sm = cv2.GaussianBlur(img, (0, 0), 1.0)
    gx = cast(FloatImage, cv2.Sobel(sm, cv2.CV_32F, 1, 0, ksize=3))
    gy = cast(FloatImage, cv2.Sobel(sm, cv2.CV_32F, 0, 1, ksize=3))
    gxx = masked_blur(gx * gx, mask, sigma)
    gyy = masked_blur(gy * gy, mask, sigma)
    gxy = masked_blur(gx * gy, mask, sigma)
    return cast(FloatImage, (0.5 * np.arctan2(2 * gxy, gxx - gyy)) % math.pi)


def oriented_filter(img: FloatImage, phi: FloatImage, kernels: list[FloatImage]) -> tuple[FloatImage, FloatImage]:
    """Filter each pixel with the Gabor kernel matching its ridge direction (interpolated).

    Returns the filtered image and the summed power of all orientations: comparing the
    two tells real ridges (power in one direction) from noise (power in every direction).
    """
    n = len(kernels)
    pos = phi * (n / math.pi)
    k0 = np.floor(pos).astype(np.int32) % n
    w1 = (pos - np.floor(pos)).astype(np.float32)
    k1 = (k0 + 1) % n
    out = np.zeros_like(img)
    power = np.zeros_like(img)
    for k, kern in enumerate(kernels):
        resp = cv2.filter2D(img, cv2.CV_32F, kern, borderType=cv2.BORDER_REFLECT)
        out += (np.where(k0 == k, 1 - w1, 0) + np.where(k1 == k, w1, 0)) * resp
        power += resp * resp
    return out, power
