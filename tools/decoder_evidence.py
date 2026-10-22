"""Evidence that a decoder upgrade (Pillow, pillow-heif) leaves Ridge's results unchanged.

Forensic standard section 13 requires revalidation when the Pillow or pillow-heif version
changes, unless the Forensic Quality Manager documents why results cannot change. The stored
goldens decode PNG only; this tool covers every allow-listed format:

    python tools/decoder_evidence.py make-inputs DIR       # synthetic inputs, written once
    python tools/decoder_evidence.py run DIR -o old.json   # in the old environment
    python tools/decoder_evidence.py run DIR -o new.json   # in the new environment
    python tools/decoder_evidence.py compare old.json new.json

`run` records for every input the SHA-256 of the file, of the decoded BGR pixels
(``ridge.image_io.decode_image``), of the photo metadata record (``ridge.metadata.read_metadata``),
of the extracted print and of the comparison export PNG a job with default settings stores
(``ridge.case.export_step``: ridge-period scale, polarity, mirror, 500 ppi). `compare` exits 1 if
any of them differs, and 2 if the two manifests come from the same versions of the image
libraries (nothing was compared). Inputs are synthetic (tests/synthetic.py,
tests/metadata_samples.py); never point this tool at case material.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import PIL
from PIL import Image, features

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]  # also runs in an environment without Ridge installed

from tests import metadata_samples  # noqa: E402
from tests.synthetic import make_photo  # noqa: E402

from ridge.case.export_step import ExportOptions, photo_scale  # noqa: E402
from ridge.errors import RidgeError  # noqa: E402
from ridge.export.png import encode_png  # noqa: E402
from ridge.export.transforms import make_comparison_export  # noqa: E402
from ridge.image_io import HEIF_AVAILABLE, ReadLimits, decode_image  # noqa: E402
from ridge.metadata import read_metadata  # noqa: E402
from ridge.pipeline.extract import ExtractionResult, extract_fingerprint  # noqa: E402

CODECS = ("jpg", "libjpeg_turbo", "zlib", "libtiff", "webp", "littlecms2")
# Environment keys whose change the evidence is about; `compare` refuses manifests where none changed.
LIBRARIES = ("pillow", "pillow_heif", "libheif", "numpy", "opencv", "codecs")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encode(im: Image.Image, fmt: str, **options: Any) -> bytes:
    buf = io.BytesIO()
    im.save(buf, fmt, **options)
    return buf.getvalue()


def _oriented(rgb: Image.Image, orientation: int) -> bytes:
    exif = Image.Exif()
    exif[0x0112] = orientation
    return _encode(rgb, "JPEG", quality=90, exif=exif)


def _inputs() -> dict[str, bytes]:
    """Synthetic inputs per allow-listed format and decoder path (name -> file bytes)."""
    bgr = make_photo("whorl", 480, 360, 9.0)
    rgb = Image.fromarray(np.ascontiguousarray(bgr[:, :, ::-1]))
    grey = rgb.convert("L")
    files: dict[str, bytes] = {
        "jpeg_q95_444.jpg": _encode(rgb, "JPEG", quality=95, subsampling=0),
        "jpeg_q85_420.jpg": _encode(rgb, "JPEG", quality=85, subsampling=2),
        "jpeg_progressive.jpg": _encode(rgb, "JPEG", quality=90, progressive=True, optimize=True),
        "jpeg_grey.jpg": _encode(grey, "JPEG", quality=90),
        "jpeg_cmyk.jpg": _encode(rgb.convert("CMYK"), "JPEG", quality=90),
        "png_rgb.png": _encode(rgb, "PNG"),
        "png_rgba.png": _encode(rgb.convert("RGBA"), "PNG"),
        "png_grey.png": _encode(grey, "PNG"),
        "png_palette.png": _encode(rgb.convert("P", palette=Image.Palette.ADAPTIVE), "PNG"),
        "png_grey16.png": _encode(Image.fromarray(np.asarray(grey, dtype=np.uint16) * 257), "PNG"),
        "png_rgb16.png": bytes(cv2.imencode(".png", bgr.astype(np.uint16) * 257)[1]),
        "tiff_raw.tif": _encode(rgb, "TIFF"),
        "tiff_lzw.tif": _encode(rgb, "TIFF", compression="tiff_lzw"),
        "tiff_deflate.tif": _encode(rgb, "TIFF", compression="tiff_adobe_deflate"),
        "tiff_cmyk.tif": _encode(rgb.convert("CMYK"), "TIFF", compression="packbits"),
        "bmp_rgb.bmp": _encode(rgb, "BMP"),
        "bmp_palette.bmp": _encode(rgb.convert("P", palette=Image.Palette.ADAPTIVE), "BMP"),
        "webp_lossy.webp": _encode(rgb, "WEBP", quality=80, method=6),
        "webp_lossless.webp": _encode(rgb, "WEBP", lossless=True),
        "meta_full.jpg": metadata_samples.full_jpeg(),
        "meta_iptc.jpg": metadata_samples.iptc_jpeg(),
        "meta_gps.png": metadata_samples.finger_png_with_gps(),
    }
    files.update({f"jpeg_orientation_{n}.jpg": _oriented(rgb, n) for n in range(1, 9)})
    if HEIF_AVAILABLE:
        files["heic_q90.heic"] = _encode(rgb, "HEIF", quality=90)
    return files


def _attempt(step: Callable[[], dict[str, str]]) -> dict[str, str]:
    """Run one evidence step; a typed Ridge refusal is part of the evidence, not a failure."""
    try:
        return step()
    except RidgeError as exc:
        return {"error": type(exc).__name__}


def _record(data: bytes) -> dict[str, str]:
    """Hashes of what Ridge makes of one input file."""
    entry = {"file": _sha(data)}
    pixels = decode_image(data, ReadLimits())
    entry["decoded"] = _sha(repr((pixels.shape, str(pixels.dtype))).encode() + pixels.tobytes())
    meta = read_metadata(data)
    entry["metadata"] = _sha(json.dumps(meta, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())

    def extract() -> dict[str, str]:
        result = extract_fingerprint(pixels)
        return {"print": _sha(result.image.tobytes()), **_attempt(partial(_export, result))}

    entry.update(_attempt(extract))
    return entry


def _export(result: ExtractionResult) -> dict[str, str]:
    """Hash the comparison export a job with default settings writes (``ridge.case.export_step``).

    Ridge-period scale, dark ridges, mirrored, 500 ppi, encoded as the PNG the job stores.
    """
    options = ExportOptions()
    exported = make_comparison_export(
        result, photo_scale(result, options), mirror_image=options.mirror, target_ppi=options.target_ppi
    )
    return {"export_png": _sha(encode_png(exported.image, exported.ppi))}


def _environment() -> dict[str, Any]:
    heif: dict[str, str] = {}
    if HEIF_AVAILABLE:
        import pillow_heif  # type: ignore[import-not-found,unused-ignore]  # optional extra  # noqa: PLC0415

        heif = {"pillow_heif": pillow_heif.__version__, "libheif": pillow_heif.libheif_version()}
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "pillow": PIL.__version__,
        "codecs": {name: features.version(name) for name in CODECS},
        **heif,
    }


def make_inputs(folder: Path) -> int:
    """Write the synthetic inputs into an empty or new folder."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in _inputs().items():
        (folder / name).write_bytes(data)
    print(f"wrote {len(list(folder.iterdir()))} synthetic inputs to {folder}")
    return 0


def run(folder: Path, out: Path) -> int:
    """Record the hashes of every input in `folder` with the installed decoders."""
    paths = sorted(p for p in folder.iterdir() if p.is_file())
    files = {p.name: _attempt(partial(_record, p.read_bytes())) for p in paths}
    manifest = {"environment": _environment(), "files": files}
    out.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    print(f"recorded {len(files)} inputs with Pillow {PIL.__version__} in {out}")
    return 0


def compare(old: Path, new: Path) -> int:
    """Print every difference between two manifests; 1 if results differ, 2 if no library changed."""
    a, b = (json.loads(p.read_bytes()) for p in (old, new))
    for key in sorted(set(a["environment"]) | set(b["environment"])):
        if a["environment"].get(key) != b["environment"].get(key):
            print(f"environment {key}: {a['environment'].get(key)} -> {b['environment'].get(key)}")
    if all(a["environment"].get(k) == b["environment"].get(k) for k in LIBRARIES):
        # Two runs in the same environment prove nothing about an upgrade.
        print(f"no change in {', '.join(LIBRARIES)}: the manifests do not compare two versions")
        return 2
    names = sorted(set(a["files"]) | set(b["files"]))
    differ = [n for n in names if a["files"].get(n) != b["files"].get(n)]
    for name in differ:
        print(f"DIFFERENT {name}: {a['files'].get(name)} -> {b['files'].get(name)}")
    print(f"{len(names) - len(differ)} of {len(names)} inputs give identical results")
    return 1 if differ else 0


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("make-inputs").add_argument("folder", type=Path)
    run_p = sub.add_parser("run")
    run_p.add_argument("folder", type=Path)
    run_p.add_argument("-o", "--out", type=Path, required=True)
    cmp_p = sub.add_parser("compare")
    cmp_p.add_argument("old", type=Path)
    cmp_p.add_argument("new", type=Path)
    args = ap.parse_args(argv)
    if args.command == "make-inputs":
        return make_inputs(args.folder)
    if args.command == "run":
        return run(args.folder, args.out)
    return compare(args.old, args.new)


if __name__ == "__main__":
    sys.exit(main())
