"""The v0 function signature, kept for code written against ``fingerprint_extract.py``."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from ridge.arrays import ImageU8
from ridge.debug import write_debug
from ridge.pipeline import extract_fingerprint as _extract


class LegacyInfo(TypedDict):
    """The v0 info dict."""

    period: float
    found_finger: bool


def extract_fingerprint(  # noqa: PLR0917  # positional parameters are the v0 public signature
    bgr: ImageU8,
    period: float | None = None,
    min_quality: float = 0.25,
    flip: bool = False,
    crop: bool = True,
    debug: tuple[str, Path] | None = None,
) -> tuple[ImageU8, LegacyInfo]:
    """Return (white-on-black uint8 image, info dict); `debug` is (stem, folder) as in v0."""
    result = _extract(bgr, period=period, min_quality=min_quality, flip=flip, crop=crop, debug=debug is not None)
    if debug is not None and result.debug is not None:
        stem, folder = debug
        write_debug(result.debug, stem, Path(folder))
    return result.image, {"period": result.period, "found_finger": result.found_finger}
