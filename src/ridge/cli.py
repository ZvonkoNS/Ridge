"""Command-line interface: ``ridge photo.jpg`` / ``python -m ridge`` / ``fingerprint_extract.py``.

Exit codes: 0 every photo succeeded, 1 at least one photo failed, 2 usage or configuration
error, 3 internal error (a bug: please report it with the ``--verbose`` output).
"""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from ridge.debug import DEBUG_TAG, debug_paths, write_debug
from ridge.errors import OutputExistsError, RidgeError
from ridge.image_io import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_PIXELS,
    HARD_MAX_BYTES,
    HARD_MAX_PIXELS,
    IMAGE_EXTS,
    MiB,
    ReadLimits,
    load_image,
    save_image,
)
from ridge.pipeline import extract_fingerprint
from ridge.terminal import safe

OUT_TAG = "_fingerprint"  # output: <photo>_fingerprint.png
EXIT_OK, EXIT_FAILURES, EXIT_INTERNAL = 0, 1, 3
RND_NOTICE = (
    "note: R&D mode, not for casework: outputs are not encrypted, hashed or logged. "
    "Use `ridge-case` for case material (PRD FR-27)."
)


def _warn(message: str, *, lines: bool = False) -> None:
    print(safe(message, lines=lines), file=sys.stderr)  # file names are attacker-controlled (CWE-150)


def is_own_output(path: Path) -> bool:
    """Return True for files named like Ridge outputs (skipped in folder mode)."""
    return path.stem.endswith(OUT_TAG) or DEBUG_TAG in path.stem


def collect_inputs(paths: Sequence[str]) -> list[Path]:
    """Expand files and folders into the list of photos to process, reporting what is skipped."""
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.suffix.lower() not in IMAGE_EXTS:
                    continue
                if f.is_symlink() or not f.is_file():  # CWE-59: never follow links found in folders
                    _warn(f"skipped {f}: not a regular file")
                elif is_own_output(f):  # so re-runs don't process their own outputs
                    _warn(f"skipped {f}: named like a Ridge output")
                else:
                    files.append(f)
        elif p.is_file():
            files.append(p)
        else:
            _warn(f"warning: {p} not found, skipped")
    return files


def output_conflict(outdir: Path, inputs: Sequence[str]) -> str | None:
    """Explain why `outdir` must not be used, or return None.

    Outputs never go into an input folder (or the folder of an input file), so folders of
    original evidence are never written to (write-path audit W1).
    """
    # Compare both the paths as given and with links resolved, so a symlinked input or output
    # folder cannot hide that outputs would land next to evidence.
    outs = {outdir.absolute(), outdir.resolve()}
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            folders, inside = {path.absolute(), path.resolve()}, True
            what = f"inside the input folder {path}"
        elif path.is_file() or path.is_symlink():
            folders, inside = {path.absolute().parent, path.resolve().parent}, False
            what = f"the folder of the input {path}"
        else:
            continue
        for out in outs:
            if any(out == f or (inside and f in out.parents) for f in folders):
                return f"output folder {outdir} is {what}: choose a separate folder"
    return None


def _bounded(kind: Callable[[str], float], low: float, high: float, unit: str) -> Callable[[str], float]:
    def parse(text: str) -> float:
        try:
            value = kind(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"must be between {low:g} and {high:g}{unit}")
        return value

    return parse


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (v0 options plus the hardening options)."""
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
        "--period",
        type=_bounded(float, 0.5, 500.0, " px"),
        help="ridge spacing in pixels in the photo (default: measured automatically)",
    )
    ap.add_argument(
        "--min-quality",
        type=_bounded(float, 0.0, 1.0, ""),
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
    ap.add_argument("--overwrite", action="store_true", help="replace existing outputs (default: refuse)")
    ap.add_argument(
        "--max-input-mb",
        type=_bounded(float, 1, HARD_MAX_BYTES / MiB, " MiB"),
        default=DEFAULT_MAX_BYTES / MiB,
        help=f"largest input file accepted (default: {DEFAULT_MAX_BYTES // MiB} MiB)",
    )
    ap.add_argument(
        "--max-megapixels",
        type=_bounded(float, 0.01, HARD_MAX_PIXELS / 1e6, " MP"),
        default=DEFAULT_MAX_PIXELS / 1e6,
        help=f"largest image accepted (default: {DEFAULT_MAX_PIXELS // 1_000_000} MP)",
    )
    ap.add_argument("--verbose", action="store_true", help="print tracebacks for internal errors")
    return ap


def _process(f: Path, outdir: Path, args: argparse.Namespace, limits: ReadLimits) -> None:
    out = outdir / f"{f.stem}{OUT_TAG}.png"
    targets = [out, *(debug_paths(f.stem, outdir) if args.debug else [])]
    if not args.overwrite:
        existing = [t.name for t in targets if t.exists()]
        if existing:  # fail fast; publishing is still no-clobber if a file appears meanwhile
            raise OutputExistsError(f"{', '.join(existing)} already exists (use --overwrite to replace it)")
    result = extract_fingerprint(
        load_image(f, limits),
        period=args.period,
        min_quality=args.min_quality,
        flip=args.flip,
        crop=not args.no_crop,
        debug=args.debug,
    )
    if result.debug is not None:
        write_debug(result.debug, f.stem, outdir, overwrite=args.overwrite)
    save_image(out, result.image, overwrite=args.overwrite)
    note = "" if result.found_finger else "  (couldn't find the finger by skin colour; searched the whole photo)"
    height, width = result.image.shape[:2]
    print(safe(f"{f} -> {out}  [ridge spacing {result.period:.1f}px, {width}x{height}]{note}"))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code (see module docstring)."""
    ap = build_parser()
    args = ap.parse_args(argv)
    limits = ReadLimits(max_bytes=int(args.max_input_mb * MiB), max_pixels=int(args.max_megapixels * 1e6))
    _warn(RND_NOTICE)

    outdir = Path(args.outdir)
    files = collect_inputs(args.inputs)
    if not files:
        ap.error("no images found")
    conflict = output_conflict(outdir, args.inputs)
    if conflict:
        ap.error(conflict)
    try:  # created only after the inputs are validated
        outdir.mkdir(mode=0o700, parents=True, exist_ok=True)  # biometric outputs: owner-only on POSIX
    except OSError as exc:
        ap.error(f"cannot create output folder {outdir}: {exc.strerror}")

    code = EXIT_OK
    for f in files:
        try:
            _process(f, outdir, args, limits)
        except RidgeError as exc:
            code = max(code, EXIT_FAILURES)
            _warn(f"{f}: FAILED - {exc}")
        except OSError as exc:
            code = max(code, EXIT_FAILURES)
            _warn(f"{f}: FAILED - {exc.strerror or type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001  # a bug: report it, keep processing the batch, exit 3
            code = EXIT_INTERNAL
            _warn(f"{f}: FAILED - internal error ({type(exc).__name__}); rerun with --verbose and report it")
            if args.verbose:
                _warn(traceback.format_exc().rstrip(), lines=True)
    return code
