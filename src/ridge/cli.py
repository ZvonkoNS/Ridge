"""Command-line interface: ``ridge photo.jpg`` / ``python -m ridge`` / ``fingerprint_extract.py``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ridge.debug import DEBUG_TAG, write_debug
from ridge.image_io import IMAGE_EXTS, load_image, save_image
from ridge.pipeline import extract_fingerprint

OUT_TAG = "_fingerprint"  # output: <photo>_fingerprint.png


def collect_inputs(paths: Sequence[str]) -> list[Path]:
    """Expand files and folders into the list of photos to process."""
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():  # skip this script's own outputs so re-runs don't process them
            files += sorted(
                f
                for f in p.iterdir()
                if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith(OUT_TAG) and DEBUG_TAG not in f.stem
            )
        elif p.is_file():
            files.append(p)
        else:
            print(f"warning: {p} not found, skipped", file=sys.stderr)
    return files


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (options match v0)."""
    ap = argparse.ArgumentParser(
        description="Extract fingerprints from finger photos as white ridges on a black background."
    )
    ap.add_argument("inputs", nargs="+", help="image files and/or folders of images")
    ap.add_argument("-o", "--outdir", default="fingerprints", help="output folder (default: ./fingerprints)")
    ap.add_argument(
        "--flip",
        action="store_true",
        help="swap ridges and valleys (e.g. for scans of ink prints, where ridges are dark)",
    )
    ap.add_argument(
        "--period", type=float, help="ridge spacing in pixels in the photo (default: measured automatically)"
    )
    ap.add_argument(
        "--min-quality",
        type=float,
        default=0.25,
        help="0..1, how clear the ridges must be to be kept; lower keeps more of the "
        "finger but may add fake ridges (default: 0.25)",
    )
    ap.add_argument("--no-crop", action="store_true", help="keep the full photo frame instead of cropping")
    ap.add_argument(
        "--debug",
        action="store_true",
        help="also save intermediate images (the green outline in *_debug_region.jpg "
        "shows which part of the photo was used)",
    )
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; returns 0 if every photo succeeded, 1 if any failed (2 = usage error)."""
    ap = build_parser()
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
            result = extract_fingerprint(
                bgr,
                period=args.period,
                min_quality=args.min_quality,
                flip=args.flip,
                crop=not args.no_crop,
                debug=args.debug,
            )
            if result.debug is not None:
                write_debug(result.debug, f.stem, outdir)
        except Exception as exc:  # noqa: BLE001  # v0 behaviour; narrowed by the hardening step
            failures += 1
            print(f"{f}: FAILED - {exc}", file=sys.stderr)
            continue
        out = outdir / f"{f.stem}{OUT_TAG}.png"
        save_image(out, result.image)
        note = "" if result.found_finger else "  (couldn't find the finger by skin colour; searched the whole photo)"
        height, width = result.image.shape[:2]
        print(f"{f} -> {out}  [ridge spacing {result.period:.1f}px, {width}x{height}]{note}")
    return 1 if failures else 0
