"""Lossless 8-bit grayscale PNG for comparison exports, with the resolution recorded (FR-32).

The PNG is encoded from pixels only. It contains IHDR, pHYs (the resolution), IDAT and IEND
and nothing else: no text chunks, EXIF, ICC profile or timestamp, and nothing from the
original photo (data minimisation). Writing the bytes is left to ``ridge.image_io.publish``
(atomic, never a silent overwrite), so the caller can hash exactly what it writes.
"""

from __future__ import annotations

import io
from typing import Final

import numpy as np
from PIL import Image

from ridge.arrays import ImageU8
from ridge.export.validate import gray_u8, ppi_value

# zlib level stated explicitly so the encoding does not depend on Pillow's default. File bytes
# can still change with the zlib version; the pixel hash is the reproducibility reference.
PNG_COMPRESS_LEVEL: Final = 6


def encode_png(image: ImageU8, ppi: float) -> bytes:
    """Encode an H x W uint8 grayscale image as PNG whose pHYs chunk says `ppi` pixels per inch.

    pHYs stores whole pixels per metre: 500 ppi is written as 19685 px/m (499.999 ppi).
    Raises ParameterError for a non-grayscale or empty image or a resolution outside
    1..100000 ppi.
    """
    pixels = np.ascontiguousarray(gray_u8(image))
    resolution = ppi_value(ppi, "ppi")
    buffer = io.BytesIO()
    with Image.fromarray(pixels) as im:  # 2-D uint8 -> mode "L" (8-bit grayscale)
        im.save(buffer, format="PNG", dpi=(resolution, resolution), compress_level=PNG_COMPRESS_LEVEL)
    return buffer.getvalue()
