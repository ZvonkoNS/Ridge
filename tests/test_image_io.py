"""Image decoding limits, format allow-list and safe publishing (PRD FR-8 to FR-12)."""

from __future__ import annotations

import io
import os
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ridge import DecodeError, InputRejectedError, OutputExistsError
from ridge.image_io import ReadLimits, decode_image, load_image, publish, read_bounded, save_image


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_header_only(width: int, height: int) -> bytes:
    """A tiny PNG whose header claims `width` x `height`: a decompression-bomb probe."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b""))
        + png_chunk(b"IEND", b"")
    )


def png_chunk_types(data: bytes) -> list[bytes]:
    types, pos = [], 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        types.append(data[pos + 4 : pos + 8])
        pos += 12 + length
    return types


def jpeg_bytes(size: tuple[int, int] = (64, 64), exif: Image.Exif | None = None) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (90, 120, 200)).save(buf, format="JPEG", exif=exif or Image.Exif())
    return buf.getvalue()


# ---------------------------------------------------------------- reading


def test_png_round_trip(tmp_path: Path) -> None:
    img = np.zeros((40, 50, 3), np.uint8)
    img[2:5, 3:9] = (10, 200, 30)
    path = tmp_path / "x.png"
    save_image(path, img)
    assert np.array_equal(load_image(path), img)


def test_rgb_becomes_bgr(tmp_path: Path) -> None:
    path = tmp_path / "red.png"
    Image.new("RGB", (40, 40), (255, 0, 0)).save(path)
    assert load_image(path)[0, 0].tolist() == [0, 0, 255]


def test_exif_orientation_is_applied(tmp_path: Path) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW to display
    path = tmp_path / "rotated.jpg"
    path.write_bytes(jpeg_bytes((80, 40), exif))
    assert load_image(path).shape == (80, 40, 3)


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("gif.jpg", None),  # GIF content with a .jpg extension
        ("eps.jpg", b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 64 64\nshowpage\n"),  # would reach Ghostscript
        ("text.png", b"this is not an image"),
        ("psd.jpg", b"8BPS\x00\x01" + b"\x00" * 64),
    ],
)
def test_disallowed_formats_are_rejected_by_content(tmp_path: Path, name: str, payload: bytes | None) -> None:
    path = tmp_path / name
    if payload is None:
        Image.new("RGB", (64, 64)).save(path, format="GIF")
    else:
        path.write_bytes(payload)
    with pytest.raises(InputRejectedError, match="not a supported image"):
        load_image(path)


def test_file_size_limit_is_checked_before_reading(tmp_path: Path) -> None:
    path = tmp_path / "big.jpg"
    path.write_bytes(jpeg_bytes((400, 400)))
    with pytest.raises(InputRejectedError, match="limit is"):
        read_bounded(path, max_bytes=1000)


@pytest.mark.parametrize(
    ("width", "height", "message"), [(13_000, 12_500, "the limit is 150 MP"), (30_000, 30_000, "")]
)
def test_decompression_bombs_are_rejected_before_decoding(width: int, height: int, message: str) -> None:
    with pytest.raises(InputRejectedError, match=message or None):
        decode_image(png_header_only(width, height), ReadLimits())


def test_pixel_limit_is_configurable() -> None:
    with pytest.raises(InputRejectedError, match="the limit is 0 MP"):
        decode_image(png_header_only(200, 200), ReadLimits(max_pixels=10_000))


def test_tiny_images_are_rejected() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    with pytest.raises(InputRejectedError, match="at least 32 px"):
        decode_image(buf.getvalue(), ReadLimits())


def test_truncated_image_is_a_decode_error() -> None:
    data = jpeg_bytes((256, 256))
    with pytest.raises(DecodeError, match="corrupt or truncated"):
        decode_image(data[: len(data) // 2], ReadLimits())


def test_corrupt_png_is_a_decode_error() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, format="PNG")
    data = bytearray(buf.getvalue())
    data[60:80] = b"\xff" * 20  # damage the compressed pixel data
    with pytest.raises(DecodeError):
        decode_image(bytes(data), ReadLimits())


def test_directories_are_not_read(tmp_path: Path) -> None:
    with pytest.raises((InputRejectedError, OSError)):
        read_bounded(tmp_path, max_bytes=1000)


@pytest.mark.parametrize(("max_bytes", "max_pixels"), [(0, 1), (1, 0), (2**40, 1), (1, 10**12)])
def test_read_limits_cannot_exceed_hard_caps(max_bytes: int, max_pixels: int) -> None:
    with pytest.raises(ValueError, match="must be in"):
        ReadLimits(max_bytes=max_bytes, max_pixels=max_pixels)


def test_errors_stay_value_errors_for_v0_callers(tmp_path: Path) -> None:
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"this is not an image")
    with pytest.raises(ValueError, match="not a supported image"):
        load_image(path)


# ---------------------------------------------------------------- writing


def test_outputs_carry_no_source_metadata(tmp_path: Path) -> None:
    exif = Image.Exif()
    exif[0x8825] = {2: (46.0, 3.0, 0.0)}  # GPS latitude in the source photo
    src = tmp_path / "photo.jpg"
    src.write_bytes(jpeg_bytes((64, 64), exif))
    out = tmp_path / "out.png"
    save_image(out, load_image(src))
    assert set(png_chunk_types(out.read_bytes())) <= {b"IHDR", b"IDAT", b"IEND"}


def test_publish_refuses_to_replace(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"original")
    with pytest.raises(OutputExistsError, match="--overwrite"):
        publish(target, b"new")
    assert target.read_bytes() == b"original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.png"]  # no temporary file left behind


def test_publish_overwrite_replaces(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"original")
    publish(target, b"new", overwrite=True)
    assert target.read_bytes() == b"new"


def test_publish_without_hard_links_falls_back_to_exclusive_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_links(src: object, dst: object) -> None:
        raise OSError("hard links not supported")

    monkeypatch.setattr(os, "link", no_links)
    target = tmp_path / "out.png"
    publish(target, b"data")
    assert target.read_bytes() == b"data"
    with pytest.raises(OutputExistsError):
        publish(target, b"again")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.png"]


def test_failed_write_leaves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def disk_full(fd: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", disk_full)
    with pytest.raises(OSError, match="No space"):
        publish(tmp_path / "out.png", b"data")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_outputs_are_owner_only_on_posix(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    publish(target, b"data")
    assert target.stat().st_mode & 0o077 == 0
