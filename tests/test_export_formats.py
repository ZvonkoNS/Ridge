"""Exchange formats for exported images (PRD FR-32): lossless TIFF and BMP with the resolution, nothing else."""

from __future__ import annotations

import io
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from PIL import Image, TiffImagePlugin

from ridge.errors import DecodeError, InputRejectedError, ParameterError
from ridge.export import encode_png
from ridge.export.formats import (
    EXTENSIONS,
    FORMATS,
    FileFormat,
    check_format,
    convert_png,
    decode_gray_png,
    encode_bmp,
    encode_tiff,
    format_for,
)
from tests.synthetic import ImageU8

TIFF_COMPRESSION, TIFF_X_RESOLUTION, TIFF_RESOLUTION_UNIT = 259, 282, 296
# Tags an uncompressed baseline grayscale TIFF needs; anything else would be metadata Ridge must not add.
BASELINE_TAGS = {256, 257, 258, 259, 262, 273, 277, 278, 279, 282, 283, 284, 296}


def pattern(height: int = 48, width: int = 64) -> ImageU8:
    yy, xx = np.mgrid[0:height, 0:width]
    return cast(ImageU8, ((5 * xx + 3 * yy) % 256).astype(np.uint8))


@pytest.fixture
def png() -> bytes:
    return encode_png(pattern(), 500.0)


def test_suffixes_and_formats() -> None:
    assert format_for(Path("a.TIF")) == "tiff"
    assert format_for(Path("a.tiff")) == "tiff"
    assert format_for(Path("a.bmp")) == "bmp"
    assert format_for(Path("a.png")) == "png"
    assert format_for(Path("a.json")) is None
    assert FORMATS == ("png", "tiff", "bmp")
    assert EXTENSIONS == {"png": ".png", "tiff": ".tif", "bmp": ".bmp"}
    assert check_format("bmp") == "bmp"
    with pytest.raises(ParameterError, match="one of"):
        check_format("jp2")


def test_tiff_is_lossless_uncompressed_and_carries_only_the_resolution(png: bytes) -> None:
    tiff = convert_png(png, "tiff")
    assert convert_png(png, "tiff") == tiff  # deterministic bytes
    with Image.open(io.BytesIO(tiff), formats=["TIFF"]) as im:
        assert im.mode == "L"
        assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)
        assert isinstance(im, TiffImagePlugin.TiffImageFile)
        tags = dict(im.tag_v2)
        assert tags[TIFF_COMPRESSION] == 1  # no compression
        assert tags[TIFF_RESOLUTION_UNIT] == 2  # inch
        assert float(tags[TIFF_X_RESOLUTION]) == pytest.approx(500.0, abs=0.1)
        assert set(tags) <= BASELINE_TAGS
        assert np.array_equal(np.asarray(im), pattern())


def test_bmp_is_lossless_with_pixels_per_metre(png: bytes) -> None:
    bmp = convert_png(png, "bmp")
    assert bmp.startswith(b"BM")
    with Image.open(io.BytesIO(bmp), formats=["BMP"]) as im:
        assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)
        assert np.array_equal(np.asarray(im.convert("L")), pattern())


def test_png_is_returned_as_stored(png: bytes) -> None:
    assert convert_png(png, "png") is png


def test_conversion_refusals() -> None:
    with pytest.raises(ParameterError, match="only a stored PNG"):
        convert_png(b"BM" + b"\0" * 64, "tiff")
    colour = io.BytesIO()
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(colour, format="PNG", dpi=(500, 500))
    with pytest.raises(ParameterError, match="not 8-bit grayscale"):
        convert_png(colour.getvalue(), "tiff")
    no_resolution = io.BytesIO()
    Image.fromarray(pattern()).save(no_resolution, format="PNG")
    with pytest.raises(ParameterError, match="records no resolution"):
        convert_png(no_resolution.getvalue(), "bmp")
    big = encode_png(pattern(40, 40), 500.0)
    with pytest.raises(InputRejectedError, match="conversion limit"):
        decode_gray_png(big, max_pixels=1000)
    truncated = encode_png(pattern(), 500.0)[:60]
    with pytest.raises(DecodeError):
        decode_gray_png(truncated)
    with pytest.raises(ParameterError, match="one of"):
        convert_png(encode_png(pattern(), 500.0), cast(FileFormat, "jp2"))


def test_encoders_validate_their_arguments() -> None:
    with pytest.raises(ParameterError):
        encode_tiff(cast(ImageU8, np.zeros((4, 4), np.float32)), 500.0)
    with pytest.raises(ParameterError):
        encode_bmp(pattern(), 0.0)
