#!/usr/bin/env python3
"""Extract fingerprints from photos of fingers: white ridges on a black background.

How it works
  1. Find the finger by skin colour (Lab a* channel + Otsu threshold).
  2. Measure the ridge spacing with local Fourier analysis and rescale the photo so
     ridges are a fixed number of pixels apart, which makes every later step
     independent of camera resolution and distance.
  3. Flatten lighting and contrast, estimate the local ridge direction and run an
     orientation-adaptive Gabor filter bank (Hong, Wan & Jain, 1998).
  4. Keep only the area where a clear ridge pattern was found, binarize it and
     save the ridges as white on black.

Usage
  python fingerprint_extract.py photo.jpg
  python fingerprint_extract.py photos/ -o prints/ --debug

Requires: pip install numpy opencv-python pillow
Optional: pip install pillow-heif   (to read iPhone .HEIC photos)
"""

import argparse
import math
import sys
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}
OUT_TAG = "_fingerprint"  # output: <photo>_fingerprint.png
DEBUG_TAG = "_debug_"  # --debug: <photo>_debug_<step>.png
WORK_PERIOD = 12.0  # ridge spacing in pixels that the photo is rescaled to for filtering
N_ORIENT = 16  # orientations in the Gabor filter bank


# --------------------------------------------------------------------------- helpers

def load_image(path):
    """Read a photo as BGR uint8, honouring the EXIF rotation that phones write."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None
    if Image is not None:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        try:
            with Image.open(path) as im:
                rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            pass  # fall through to OpenCV
    # np.fromfile + imdecode also copes with non-ASCII paths on Windows.
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        hint = " (for .HEIC: pip install pillow pillow-heif)" if path.suffix.lower() in {".heic", ".heif"} else ""
        raise ValueError(f"cannot read image{hint}")
    return img


def save_image(path, img):
    ok, buf = cv2.imencode(path.suffix or ".png", img)
    if not ok:
        raise ValueError(f"cannot encode {path}")
    buf.tofile(str(path))


def masked_blur(img, mask, sigma):
    """Gaussian blur that only averages pixels inside `mask` (no halos at the finger edge)."""
    num = cv2.GaussianBlur(img * mask, (0, 0), sigma)
    den = cv2.GaussianBlur(mask, (0, 0), sigma)
    return num / np.maximum(den, 1e-3)


def disk(diameter):
    d = max(3, int(round(diameter)) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d))


def largest_component(mask):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 1:
        return mask.astype(bool)
    return labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))


def fill_holes(mask):
    n, labels = cv2.connectedComponents((~mask).astype(np.uint8), connectivity=4)
    outside = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    return mask | ~np.isin(labels, outside)


def remove_specks(binary, min_area):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[labels]


# --------------------------------------------------------------------------- pipeline steps

def finger_mask(bgr):
    """Finger silhouette from skin colour, or None if skin and background don't separate."""
    h, w = bgr.shape[:2]
    s = 512.0 / max(h, w)
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    a = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2LAB)[:, :, 1], (0, 0), 2)
    _, m = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = m > 0
    # Otsu always splits the histogram; accept only a clear skin-vs-background split.
    if not 0.03 < m.mean() < 0.97:
        return None
    a = a.astype(np.float32)
    separability = m.mean() * (1 - m.mean()) * (a[m].mean() - a[~m].mean()) ** 2 / (a.var() + 1e-6)
    if separability < 0.75 or a[m].mean() - a[~m].mean() < 5:
        return None
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, disk(7))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disk(7))
    m = fill_holes(largest_component(m))
    return cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR) > 0


def estimate_period(gray, mask):
    """Dominant ridge spacing in pixels, from the spectra of small patches on the finger."""
    # Rescale so the finger is ~640 px wide; a finger is roughly 25-60 ridges wide,
    # so one patch size and one search band then fit photos of any resolution.
    dist = cv2.distanceTransform(np.pad(mask, 1).astype(np.uint8), cv2.DIST_L2, 5)
    s = 640.0 / max(2.0 * float(dist.max()), 1.0)
    g = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    m = cv2.resize(mask.astype(np.uint8), (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST)
    g = g - cv2.GaussianBlur(g, (0, 0), 6)  # drop lighting gradients

    size, step, nfft = 96, 24, 256
    win = np.outer(np.hanning(size), np.hanning(size)).astype(np.float32)
    fy = np.fft.fftfreq(nfft)[:, None]
    fx = np.fft.rfftfreq(nfft)[None, :]
    radius = np.hypot(fx, fy)
    band = (radius > 1 / 40) & (radius < 1 / 3.5)  # ~16..180 ridges across the finger
    band_radius = radius[band]
    whiten = band_radius ** 2  # flattens the 1/f^2 falloff of natural images

    coverage = cv2.boxFilter(m.astype(np.float32), -1, (size, size), anchor=(0, 0), normalize=True)
    ys, xs = np.mgrid[0:g.shape[0] - size + 1:step, 0:g.shape[1] - size + 1:step]
    ys, xs = ys.ravel(), xs.ravel()
    inside = coverage[ys, xs] > 0.95
    ys, xs = ys[inside], xs[inside]
    if len(ys) < 4:  # finger too small for patches: fall back to the whole frame
        ys, xs = np.mgrid[0:g.shape[0] - size + 1:step, 0:g.shape[1] - size + 1:step]
        ys, xs = ys.ravel(), xs.ravel()
    if len(ys) == 0:
        raise ValueError("image too small to measure ridge spacing; pass --period")

    raw_periods, periods, sharpness = [], [], []
    for i in range(0, len(ys), 256):
        patches = np.stack([g[y:y + size, x:x + size] for y, x in zip(ys[i:i + 256], xs[i:i + 256])])
        patches = (patches - patches.mean(axis=(1, 2), keepdims=True)) * win
        power = (np.abs(np.fft.rfft2(patches, s=(nfft, nfft))) ** 2)[:, band]
        raw_periods.append(1.0 / band_radius[np.argmax(power, axis=1)])
        power *= whiten
        peak = np.argmax(power, axis=1)
        periods.append(1.0 / band_radius[peak])
        # Share of in-band energy at the peak: high for a clean ridge wave, tiny for noise.
        sharpness.append(power[np.arange(len(peak)), peak] / (power.sum(axis=1) + 1e-12))
    raw_periods, periods, sharpness = map(np.concatenate, (raw_periods, periods, sharpness))

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


def gabor_bank(period, n=N_ORIENT):
    """Even-symmetric Gabor kernels tuned to `period`, for n directions across the ridges.

    Also returns the total power the whole bank passes for a clean ridge wave, which
    turns the bank into a ridge-quality detector (see oriented_filter).
    """
    sx, sy = 0.45 * period, 0.65 * period  # envelope across / along the ridges
    half = int(math.ceil(3 * max(sx, sy)))
    y, x = np.mgrid[-half:half + 1, -half:half + 1].astype(np.float64)
    kernels = []
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


def ridge_orientation(img, mask, sigma):
    """Direction across the ridges (radians, 0..pi) from the smoothed structure tensor."""
    sm = cv2.GaussianBlur(img, (0, 0), 1.0)
    gx = cv2.Sobel(sm, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(sm, cv2.CV_32F, 0, 1, ksize=3)
    gxx = masked_blur(gx * gx, mask, sigma)
    gyy = masked_blur(gy * gy, mask, sigma)
    gxy = masked_blur(gx * gy, mask, sigma)
    return (0.5 * np.arctan2(2 * gxy, gxx - gyy)) % math.pi


def oriented_filter(img, phi, kernels):
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


def periodicity(enh, phi, period):
    """~1 where the ridge signal continues one ridge spacing away on both sides,
    ~0 at lone edges and creases (finger outline, background lines)."""
    energy = cv2.GaussianBlur(enh * enh, (0, 0), 0.5 * period)
    h, w = enh.shape
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    dx = (period * np.cos(phi)).astype(np.float32)
    dy = (period * np.sin(phi)).astype(np.float32)
    ahead = cv2.remap(energy, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    behind = cv2.remap(energy, xx - dx, yy - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return np.clip(np.minimum(ahead, behind) / (energy + 1e-6), 0, 1)


def extract_fingerprint(bgr, period=None, min_quality=0.25, flip=False, crop=True, debug=None):
    """Return (white-on-black uint8 image, info dict)."""
    h, w = bgr.shape[:2]
    mask = finger_mask(bgr)
    found_finger = mask is not None
    if mask is None:
        mask = np.ones((h, w), bool)
    gray = bgr[:, :, 1].astype(np.float32) / 255.0  # green shows ridges best on skin

    if period is None:
        period = estimate_period(gray, mask)
    if period < 3:
        raise ValueError(f"ridges are only {period:.1f}px apart: the photo is too low-resolution "
                         "(take it closer, or pass --period if the estimate is wrong)")

    # Work on the finger's bounding box, rescaled so ridges are WORK_PERIOD px apart.
    bx, by, bw, bh = cv2.boundingRect(mask.astype(np.uint8))
    pad = int(3 * period)
    y0, y1 = max(by - pad, 0), min(by + bh + pad, h)
    x0, x1 = max(bx - pad, 0), min(bx + bw + pad, w)
    scale = WORK_PERIOD / period
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    g = cv2.resize(gray[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=interp)
    m = cv2.resize(mask[y0:y1, x0:x1].astype(np.float32), (g.shape[1], g.shape[0]),
                   interpolation=cv2.INTER_LINEAR)
    m = (m > 0.5).astype(np.float32)
    P = WORK_PERIOD

    # 1. Flatten lighting and equalize contrast.
    hp = (g - masked_blur(g, m, 0.7 * P)) * m
    std = np.sqrt(masked_blur(hp * hp, m, 2 * P))
    norm = hp / (std + 0.05 * float(np.median(std[m > 0])) + 1e-6) * m

    # 2. Ridge direction + orientation-adaptive Gabor filtering, twice: the second
    #    pass takes its directions from the cleaner first-pass result.
    kernels, bank_power = gabor_bank(P)
    enh, _ = oriented_filter(norm, ridge_orientation(norm, m, P), kernels)
    phi = ridge_orientation(enh, m, 0.6 * P)
    enh, power = oriented_filter(norm, phi, kernels)

    # 3. Ridge quality, ~1 for clean ridges and low for noise: the share of the
    #    ridge-frequency energy that lies along the local ridge direction, and only
    #    where that pattern repeats like ridges do.
    quality = bank_power * masked_blur(enh * enh, m, 1.5 * P) / (masked_blur(power, m, 1.5 * P) + 1e-6)
    quality *= periodicity(enh, phi, P)
    quality = cv2.GaussianBlur(quality * m, (0, 0), 1.5 * P)
    inner = cv2.erode(m.astype(np.uint8), disk(3 * P)) > 0  # skip the silhouette edge
    region = ((quality > min_quality) & inner).astype(np.uint8)
    # One compact blob: cut thin necks and lobes, then fill notches and holes.
    region = cv2.morphologyEx(region, cv2.MORPH_OPEN, disk(4 * P))
    if not region.any():
        raise ValueError("no clear ridge pattern found (try a lower --min-quality or a sharper photo)")
    region = largest_component(region).astype(np.uint8)
    region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, disk(6 * P)) > 0
    region = fill_holes(region) & inner
    region = cv2.GaussianBlur(region.astype(np.float32), (0, 0), 1.5 * P)  # smooth outline

    # 4. Threshold the smooth filter output at the photo's resolution (or finer for
    #    low-res photos when cropping, so ridge edges stay smooth).
    if crop:  # just the print, plus one ridge spacing of margin
        out_scale = max(1.0, WORK_PERIOD / period)
        rx, ry, rw, rh = cv2.boundingRect((region > 0.5).astype(np.uint8))
        wx0, wy0 = max(rx - int(P), 0), max(ry - int(P), 0)
        wx1, wy1 = min(rx + rw + int(P), enh.shape[1]), min(ry + rh + int(P), enh.shape[0])
        f = out_scale / scale  # output pixels per working pixel
        size = (round((wx1 - wx0) * f), round((wy1 - wy0) * f))
    else:  # the whole finger box, pasted back into a frame the size of the photo
        out_scale = 1.0
        wx0, wy0, wx1, wy1 = 0, 0, enh.shape[1], enh.shape[0]
        size = (x1 - x0, y1 - y0)
    enh_out = cv2.resize(enh[wy0:wy1, wx0:wx1], size, interpolation=cv2.INTER_CUBIC)
    region_out = cv2.resize(region[wy0:wy1, wx0:wx1], size, interpolation=cv2.INTER_LINEAR) > 0.5
    if not region_out.any():
        raise ValueError("no clear ridge pattern found (try a lower --min-quality or a sharper photo)")
    ridges = (enh_out < 0) if flip else (enh_out > 0)  # ridges are the bright lines in a photo
    p_out = period * out_scale
    ridges = remove_specks(ridges & region_out, min_area=0.25 * p_out * p_out)
    result = ridges.astype(np.uint8) * 255
    if not crop:
        full = np.zeros((h, w), np.uint8)
        full[y0:y1, x0:x1] = result
        result = full

    if debug is not None:
        stem, folder = debug
        def to8(a, lo, hi):
            return np.clip((a - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
        overlay = bgr[y0:y1, x0:x1].copy()
        outline = cv2.resize(region, (x1 - x0, y1 - y0)) > 0.5
        contours, _ = cv2.findContours(outline.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(overlay, contours, -1, (0, 255, 0), max(2, round(period / 4)))
        save_image(folder / f"{stem}{DEBUG_TAG}region.jpg", overlay)
        save_image(folder / f"{stem}{DEBUG_TAG}normalized.png", to8(norm, -2.5, 2.5))
        save_image(folder / f"{stem}{DEBUG_TAG}gabor.png", to8(enh, -1.5, 1.5))
        save_image(folder / f"{stem}{DEBUG_TAG}quality.png", to8(quality, 0, 1))

    return result, {"period": period, "found_finger": found_finger}


# --------------------------------------------------------------------------- CLI

def collect_inputs(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():  # skip this script's own outputs so re-runs don't process them
            files += sorted(f for f in p.iterdir()
                            if f.suffix.lower() in IMAGE_EXTS
                            and not f.stem.endswith(OUT_TAG) and DEBUG_TAG not in f.stem)
        elif p.is_file():
            files.append(p)
        else:
            print(f"warning: {p} not found, skipped", file=sys.stderr)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Extract fingerprints from finger photos as white ridges on a black background.")
    ap.add_argument("inputs", nargs="+", help="image files and/or folders of images")
    ap.add_argument("-o", "--outdir", default="fingerprints",
                    help="output folder (default: ./fingerprints)")
    ap.add_argument("--flip", action="store_true",
                    help="swap ridges and valleys (e.g. for scans of ink prints, where ridges are dark)")
    ap.add_argument("--period", type=float,
                    help="ridge spacing in pixels in the photo (default: measured automatically)")
    ap.add_argument("--min-quality", type=float, default=0.25,
                    help="0..1, how clear the ridges must be to be kept; lower keeps more of the "
                         "finger but may add fake ridges (default: 0.25)")
    ap.add_argument("--no-crop", action="store_true", help="keep the full photo frame instead of cropping")
    ap.add_argument("--debug", action="store_true",
                    help="also save intermediate images (the green outline in *_debug_region.jpg "
                         "shows which part of the photo was used)")
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    files = collect_inputs(args.inputs)
    if not files:
        ap.error("no images found")

    failures = 0
    for f in files:
        try:
            bgr = load_image(f)
            result, info = extract_fingerprint(
                bgr, period=args.period, min_quality=args.min_quality, flip=args.flip,
                crop=not args.no_crop, debug=(f.stem, outdir) if args.debug else None)
        except Exception as exc:
            failures += 1
            print(f"{f}: FAILED - {exc}", file=sys.stderr)
            continue
        out = outdir / f"{f.stem}{OUT_TAG}.png"
        save_image(out, result)
        note = "" if info["found_finger"] else "  (couldn't find the finger by skin colour; searched the whole photo)"
        print(f"{f} -> {out}  [ridge spacing {info['period']:.1f}px, "
              f"{result.shape[1]}x{result.shape[0]}]{note}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
