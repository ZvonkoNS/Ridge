"""Image reading and writing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ridge.image_io import load_image, save_image


def test_png_round_trip(tmp_path: Path) -> None:
    img = np.zeros((10, 20, 3), np.uint8)
    img[2:5, 3:9] = (10, 200, 30)
    path = tmp_path / "x.png"
    save_image(path, img)
    assert np.array_equal(load_image(path), img)


def test_rgb_becomes_bgr(tmp_path: Path) -> None:
    path = tmp_path / "red.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(path)
    assert load_image(path)[0, 0].tolist() == [0, 0, 255]


def test_exif_orientation_is_applied(tmp_path: Path) -> None:
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW to display
    Image.new("RGB", (40, 20), (90, 120, 200)).save(path, exif=exif)
    assert load_image(path).shape == (40, 20, 3)


def test_unreadable_file_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"this is not an image")
    with pytest.raises(ValueError, match="cannot read image"):
        load_image(path)
