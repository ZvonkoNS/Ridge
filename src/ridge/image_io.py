"""Bounded, allow-listed image decoding and atomic, no-overwrite image writing.

Security posture (architecture §9.1, PRD FR-8 to FR-12):

* Only allow-listed formats are decoded, identified by content (Pillow ``formats=``), so
  exotic decoders such as EPS/Ghostscript are never reached, whatever the extension.
* File size is limited before reading and pixel count before decoding (CWE-400/409/770).
* There is one decoder; corrupt or truncated input raises ``DecodeError`` (no fallback).
* Outputs are encoded from pixel arrays only, so no source metadata (EXIF/GPS) is copied.
* Outputs are published atomically and never replace an existing file unless asked to.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import stat
import struct
import tempfile
import warnings
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from ridge.arrays import ImageU8
from ridge.errors import DecodeError, InputRejectedError, OutputError, OutputExistsError

try:  # optional extra: ridge[heic]
    import pillow_heif  # type: ignore[import-not-found,unused-ignore]
except ImportError:  # pragma: no cover - depends on the installed extras
    HEIF_AVAILABLE = False
else:
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True

LOG = logging.getLogger(__name__)
MiB = 1024 * 1024
DEFAULT_MAX_BYTES = 200 * MiB
DEFAULT_MAX_PIXELS = 150_000_000  # below Pillow's own decompression-bomb error threshold (~179 MP)
HARD_MAX_BYTES = 1024 * MiB  # configuration can lower limits but never exceed these
HARD_MAX_PIXELS = 170_000_000
MIN_SIDE = 32  # smaller images cannot contain a usable fingerprint

ALLOWED_FORMATS: tuple[str, ...] = ("JPEG", "PNG", "TIFF", "BMP", "WEBP") + (("HEIF",) if HEIF_AVAILABLE else ())
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"})
_FORMAT_NAMES = "JPEG, PNG, TIFF, BMP, WebP" + (", HEIF/HEIC" if HEIF_AVAILABLE else "")

# What Pillow's decoders raise on malformed data. Mapped to DecodeError at this trust
# boundary; anything else is a bug and propagates.
_DECODER_FAILURES: tuple[type[Exception], ...] = (
    OSError,
    SyntaxError,
    ValueError,
    EOFError,
    struct.error,
    IndexError,
    KeyError,
    TypeError,
    zlib.error,
)


@dataclass(frozen=True)
class ReadLimits:
    """Limits applied to every input before it is decoded."""

    max_bytes: int = DEFAULT_MAX_BYTES
    max_pixels: int = DEFAULT_MAX_PIXELS

    def __post_init__(self) -> None:
        if not 0 < self.max_bytes <= HARD_MAX_BYTES:
            raise ValueError(f"max_bytes must be in 1..{HARD_MAX_BYTES}")
        if not 0 < self.max_pixels <= HARD_MAX_PIXELS:
            raise ValueError(f"max_pixels must be in 1..{HARD_MAX_PIXELS}")


def read_bounded(path: Path, max_bytes: int) -> bytes:
    """Read a regular file of at most `max_bytes` bytes (checked before and while reading)."""
    # O_NONBLOCK: opening a FIFO or device must not hang the batch (it is rejected below).
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as fh:
        info = os.fstat(fh.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise InputRejectedError("not a regular file")
        if info.st_size > max_bytes:
            raise InputRejectedError(f"file is {info.st_size / MiB:.1f} MiB; the limit is {max_bytes / MiB:.0f} MiB")
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:  # the file grew after the size check
        raise InputRejectedError(f"file is larger than the {max_bytes / MiB:.0f} MiB limit")
    return data


def decode_image(data: bytes, limits: ReadLimits) -> ImageU8:
    """Decode allow-listed image bytes to BGR uint8, applying the EXIF orientation.

    Decoder warnings (e.g. malformed metadata) are captured and reported through
    ``logging`` rather than escaping as uncontrolled warnings; they never stop a decode
    that otherwise succeeds.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Ridge enforces its own pixel limit; Pillow's warning threshold is lower.
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        try:
            return _decode(data, limits)
        finally:
            for warning in caught:
                LOG.warning("image decoder warning: %s", warning.message)


def _decode(data: bytes, limits: ReadLimits) -> ImageU8:
    try:
        with Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS) as im:
            width, height = im.size
            if width * height > limits.max_pixels:
                raise InputRejectedError(
                    f"image is {width}x{height} ({width * height / 1e6:.0f} MP); "
                    f"the limit is {limits.max_pixels / 1e6:.0f} MP"
                )
            if min(width, height) < MIN_SIDE:
                raise InputRejectedError(f"image is {width}x{height}; at least {MIN_SIDE} px per side is needed")
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
    except InputRejectedError:
        raise
    except UnidentifiedImageError as exc:
        raise InputRejectedError(f"not a supported image ({_FORMAT_NAMES})") from exc
    except Image.DecompressionBombError as exc:
        raise InputRejectedError("image dimensions exceed the decoder's safety limit") from exc
    except _DECODER_FAILURES as exc:
        raise DecodeError("image data is corrupt or truncated") from exc
    return cast(ImageU8, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def load_image(path: Path, limits: ReadLimits | None = None) -> ImageU8:
    """Read a photo as BGR uint8 within `limits`, honouring the EXIF rotation phones write.

    Raises InputRejectedError (limits, format) or DecodeError (corrupt data); OSError for
    files that cannot be opened.
    """
    limits = limits or ReadLimits()
    return decode_image(read_bounded(path, limits.max_bytes), limits)


def encode_image(img: ImageU8, suffix: str) -> bytes:
    """Encode pixels only (no metadata) in the format given by `suffix` (.png or .jpg)."""
    ok, buf = cv2.imencode(suffix, img)
    if not ok:
        raise OutputError(f"cannot encode a {suffix} image")
    return buf.tobytes()


def publish(path: Path, data: bytes, *, overwrite: bool = False) -> None:
    """Write `data` to `path` atomically; refuse to replace an existing file unless `overwrite`.

    The bytes go to a private temporary file in the target folder first. Without
    `overwrite` the file is published with a hard link, which fails atomically if the
    target exists (no check-then-write race, CWE-367); file systems without hard links
    fall back to exclusive creation.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if overwrite:
            tmp.replace(path)
            return
        try:
            os.link(tmp, path)
        except FileExistsError:
            raise OutputExistsError(f"{path.name} already exists (use --overwrite to replace it)") from None
        except OSError:  # no hard links on this file system: exclusive create instead
            _write_exclusive(path, data)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def _write_exclusive(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except FileExistsError:
        raise OutputExistsError(f"{path.name} already exists (use --overwrite to replace it)") from None


def save_image(path: Path, img: ImageU8, *, overwrite: bool = False) -> None:
    """Encode by file extension (.png default) and publish atomically without metadata."""
    publish(path, encode_image(img, path.suffix or ".png"), overwrite=overwrite)
