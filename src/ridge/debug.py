"""Writing the intermediate images produced with ``--debug``."""

from __future__ import annotations

from pathlib import Path

from ridge.image_io import save_image
from ridge.pipeline import DebugImages

DEBUG_TAG = "_debug_"  # --debug: <photo>_debug_<step>.png


def write_debug(images: DebugImages, stem: str, folder: Path) -> None:
    """Save the debug images as <stem>_debug_<step>.(jpg|png) in `folder`."""
    save_image(folder / f"{stem}{DEBUG_TAG}region.jpg", images.region)
    save_image(folder / f"{stem}{DEBUG_TAG}normalized.png", images.normalized)
    save_image(folder / f"{stem}{DEBUG_TAG}gabor.png", images.gabor)
    save_image(folder / f"{stem}{DEBUG_TAG}quality.png", images.quality)
