"""Reading photos and writing result images."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import cv2
import numpy as np

from ridge.arrays import ImageU8

IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"})


def load_image(path: Path) -> ImageU8:
    """Read a photo as BGR uint8, honouring the EXIF rotation that phones write."""
    # v0 behaviour (lazy, optional imports); replaced by the hardening step.
    try:
        from PIL import Image, ImageOps  # noqa: PLC0415
    except ImportError:
        Image = None  # type: ignore[assignment]  # noqa: N806
    if Image is not None:
        try:
            import pillow_heif  # type: ignore[import-not-found,unused-ignore]  # noqa: PLC0415

            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        try:
            with Image.open(path) as im:
                rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
            return cast(ImageU8, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        except Exception:  # noqa: BLE001, S110  # v0 behaviour; removed by the hardening step
            pass  # fall through to OpenCV
    # np.fromfile + imdecode also copes with non-ASCII paths on Windows.
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        hint = " (for .HEIC: pip install pillow pillow-heif)" if path.suffix.lower() in {".heic", ".heif"} else ""
        raise ValueError(f"cannot read image{hint}")
    return cast(ImageU8, img)


def save_image(path: Path, img: ImageU8) -> None:
    """Encode by file extension and write (np.tofile copes with non-ASCII paths on Windows)."""
    ok, buf = cv2.imencode(path.suffix or ".png", img)
    if not ok:
        raise ValueError(f"cannot encode {path}")
    buf.tofile(str(path))
