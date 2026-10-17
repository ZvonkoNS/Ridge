"""Writing the intermediate images produced with ``--debug``."""

from __future__ import annotations

from pathlib import Path

from ridge.image_io import save_image
from ridge.pipeline import DebugImages

DEBUG_TAG = "_debug_"  # --debug: <photo>_debug_<step>.png
_STEPS = (("region", ".jpg"), ("normalized", ".png"), ("gabor", ".png"), ("quality", ".png"))


def debug_paths(stem: str, folder: Path) -> list[Path]:
    """Paths the debug images for `stem` are written to."""
    return [folder / f"{stem}{DEBUG_TAG}{step}{ext}" for step, ext in _STEPS]


def write_debug(images: DebugImages, stem: str, folder: Path, *, overwrite: bool = False) -> None:
    """Save the debug images as <stem>_debug_<step>.(jpg|png) in `folder`."""
    for (step, _), path in zip(_STEPS, debug_paths(stem, folder), strict=True):
        save_image(path, getattr(images, step), overwrite=overwrite)
