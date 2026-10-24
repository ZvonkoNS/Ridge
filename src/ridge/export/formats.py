"""Exchange file formats for exported images: PNG as stored, or uncompressed TIFF and BMP (PRD FR-32).

Not every AFIS import tool or forensic viewer accepts PNG. When an examiner exports one of Ridge's
own image outputs to a ``.tif``/``.tiff`` or ``.bmp`` destination, the stored PNG is decoded with
bounds and re-encoded from its pixels alone: 8-bit grayscale, uncompressed, with the recorded
resolution carried over (TIFF XResolution/YResolution in pixels per inch, BMP pixels per metre)
and no other metadata. The pixels are identical, so the conversion is lossless; the written file
has its own SHA-256, which the custody entry records next to the stored item's.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Final, Literal

import numpy as np
from PIL import Image

from ridge.arrays import ImageU8
from ridge.errors import DecodeError, InputRejectedError, ParameterError
from ridge.export.validate import gray_u8, ppi_value

type FileFormat = Literal["png", "tiff", "bmp"]
FORMATS: Final[tuple[FileFormat, ...]] = ("png", "tiff", "bmp")
SUFFIXES: Final[dict[str, FileFormat]] = {".png": "png", ".tif": "tiff", ".tiff": "tiff", ".bmp": "bmp"}
EXTENSIONS: Final[dict[FileFormat, str]] = {"png": ".png", "tiff": ".tif", "bmp": ".bmp"}
MAX_CONVERT_PIXELS: Final = 50_000_000  # Ridge's own exports stay under MAX_EXPORT_PIXELS
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
NO_RESOLUTION: Final = (
    "the stored image records no resolution (it is not a comparison export), so an exchange file would be "
    "read at a software default: export it as PNG"
)


def format_for(path: Path) -> FileFormat | None:
    """Return the exchange format a destination name asks for, or None for any other suffix (bytes as stored)."""
    return SUFFIXES.get(path.suffix.lower())


def check_format(value: object) -> FileFormat:
    """Return `value` as a file format, else raise ParameterError."""
    for fmt in FORMATS:
        if value == fmt:
            return fmt
    raise ParameterError(f"the file format must be one of {', '.join(FORMATS)}")


def decode_gray_png(data: bytes, max_pixels: int = MAX_CONVERT_PIXELS) -> tuple[ImageU8, float | None]:
    """Decode one of Ridge's own PNGs: (H x W uint8 pixels, the declared resolution in ppi or None).

    Only 8-bit grayscale PNG is accepted, and the pixel count is checked before the pixels are read.
    The declared resolution is rounded to 0.1 ppi (pHYs stores whole pixels per metre).
    """
    if not data.startswith(PNG_SIGNATURE):
        raise ParameterError("only a stored PNG image can be converted")
    try:
        with Image.open(io.BytesIO(data), formats=["PNG"]) as im:
            width, height = im.size
            if width * height > max_pixels:
                raise InputRejectedError(
                    f"the image is {width}x{height} px; the conversion limit is {max_pixels / 1e6:.0f} MP"
                )
            if im.mode != "L":
                raise ParameterError(f"the stored image is mode {im.mode}, not 8-bit grayscale")
            dpi = im.info.get("dpi")
            pixels = np.asarray(im, dtype=np.uint8)
    except (InputRejectedError, ParameterError):
        raise
    except (OSError, SyntaxError, ValueError, EOFError) as exc:
        raise DecodeError("the stored PNG is corrupt or truncated") from exc
    ppi = round(float(dpi[0]), 1) if dpi and float(dpi[0]) > 0 else None
    return pixels, ppi


def encode_tiff(image: ImageU8, ppi: float) -> bytes:
    """Encode 8-bit grayscale TIFF: uncompressed, resolution in pixels per inch, no other tags."""
    resolution = ppi_value(ppi, "ppi")
    buffer = io.BytesIO()
    with Image.fromarray(np.ascontiguousarray(gray_u8(image))) as im:
        im.save(buffer, format="TIFF", compression="raw", dpi=(resolution, resolution))
    return buffer.getvalue()


def encode_bmp(image: ImageU8, ppi: float) -> bytes:
    """Encode 8-bit grayscale BMP (grey palette) with the resolution as pixels per metre."""
    resolution = ppi_value(ppi, "ppi")
    buffer = io.BytesIO()
    with Image.fromarray(np.ascontiguousarray(gray_u8(image))) as im:
        im.save(buffer, format="BMP", dpi=(resolution, resolution))
    return buffer.getvalue()


def convert_png(data: bytes, fmt: FileFormat) -> bytes:
    """Re-encode a stored PNG as `fmt` with its recorded resolution; ``"png"`` returns the bytes unchanged.

    An image without a recorded resolution (the print, debug images) is refused: an exchange file
    without a true resolution would be read at a software default.
    """
    fmt = check_format(fmt)
    if fmt == "png":
        return data
    pixels, ppi = decode_gray_png(data)
    if ppi is None:
        raise ParameterError(NO_RESOLUTION)
    return encode_tiff(pixels, ppi) if fmt == "tiff" else encode_bmp(pixels, ppi)
