"""Comparison-export PNG (PRD FR-32): lossless 8-bit grayscale, pHYs resolution, no metadata.

The images are synthetic and only ever exist in memory.
"""

from __future__ import annotations

import io
import math
import struct
import zlib
from typing import cast

import numpy as np
import pytest
from PIL import Image

from ridge import ParameterError, extract_fingerprint
from ridge.export import encode_png, make_comparison_export, scale_from_ruler
from tests.golden_cases import CASES_BY_NAME
from tests.synthetic import ImageU8

FORBIDDEN_CHUNKS = (b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME", b"iCCP", b"sRGB", b"gAMA", b"cHRM", b"sBIT")


def pattern(height: int = 60, width: int = 80) -> ImageU8:
    yy, xx = np.mgrid[0:height, 0:width]
    return cast(ImageU8, ((7 * xx + 3 * yy * yy) % 256).astype(np.uint8))


def png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """Split a PNG into (type, payload) chunks, checking the signature and every CRC."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks: list[tuple[bytes, bytes]] = []
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind, payload = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        assert crc == zlib.crc32(kind + payload), kind
        chunks.append((kind, payload))
        pos += 12 + length
    assert pos == len(data)
    return chunks


@pytest.mark.parametrize(("ppi", "px_per_metre"), [(500.0, 19685), (1000, 39370), (250.0, 9843)])
def test_png_records_resolution_in_phys(ppi: float, px_per_metre: int) -> None:
    chunks = dict(png_chunks(encode_png(pattern(), ppi)))
    assert chunks[b"pHYs"] == struct.pack(">IIB", px_per_metre, px_per_metre, 1)  # unit 1: metre


def test_png_is_lossless_grayscale_without_metadata() -> None:
    image = pattern(37, 53)
    data = encode_png(image, 500.0)
    chunks = png_chunks(data)
    kinds = [kind for kind, _ in chunks]
    assert kinds[0] == b"IHDR"
    assert kinds[-1] == b"IEND"
    assert set(kinds) == {b"IHDR", b"pHYs", b"IDAT", b"IEND"}
    assert not set(kinds) & set(FORBIDDEN_CHUNKS)
    width, height, bit_depth, colour_type = struct.unpack(">IIBB", chunks[0][1][:10])
    assert (width, height, bit_depth, colour_type) == (53, 37, 8, 0)  # 8-bit grayscale
    with Image.open(io.BytesIO(data)) as im:
        assert im.format == "PNG"
        assert im.mode == "L"
        assert im.info["dpi"] == pytest.approx((500.0, 500.0), abs=0.01)
        assert np.array_equal(np.asarray(im), image)


def test_png_is_deterministic_and_accepts_views() -> None:
    image = pattern()
    view = image[:, ::-1]  # not C-contiguous
    assert encode_png(image, 500.0) == encode_png(image.copy(), 500.0)
    with Image.open(io.BytesIO(encode_png(view, 500.0))) as im:
        assert np.array_equal(np.asarray(im), view)


@pytest.mark.parametrize("bad", [0, -1.0, math.nan, math.inf, True, "500", None, 0.5, 100_001.0], ids=repr)
def test_png_rejects_bad_resolution(bad: object) -> None:
    with pytest.raises(ParameterError):
        encode_png(pattern(), cast(float, bad))


@pytest.mark.parametrize(
    "bad",
    [np.zeros((8, 8), np.uint16), np.zeros((8, 8, 3), np.uint8), np.zeros((8, 0), np.uint8), b"\x00" * 64],
    ids=["uint16", "colour", "empty", "bytes"],
)
def test_png_rejects_non_grayscale_u8(bad: object) -> None:
    with pytest.raises(ParameterError):
        encode_png(cast(ImageU8, bad), 500.0)


def test_png_of_a_full_export() -> None:
    result = extract_fingerprint(CASES_BY_NAME["arch_default"].photo())
    export = make_comparison_export(result, scale_from_ruler((0.0, 0.0), (300.0, 0.0), 15.0))
    data = encode_png(export.image, export.ppi)
    assert dict(png_chunks(data))[b"pHYs"] == struct.pack(">IIB", 19685, 19685, 1)
    with Image.open(io.BytesIO(data)) as im:
        assert np.array_equal(np.asarray(im), export.image)
