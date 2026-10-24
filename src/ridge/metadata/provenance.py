"""Provenance hints: signs that a photo is a copy or an edit rather than the camera's original (PRD FR-42).

A forwarded, resized or re-saved photo has lost detail that no extraction recovers, so the examiner
should ask for the original file from the device extraction whenever a copy is suspected. Ridge
draws hints from what the file records about itself (the metadata record of FR-36) and from how it
is encoded (its format and, for JPEG, the luminance quantisation table). They are hints: none
proves how the photo was handled, Ridge verifies none of them, and nothing is scored or concluded.
Pure and bounded: a handful of short display-safe lines built by Ridge from numbers and from values
the metadata reader already made safe.
"""

from __future__ import annotations

import io
import re
from typing import Any, Final

from PIL import Image, UnidentifiedImageError

from ridge.image_io import ALLOWED_FORMATS
from ridge.metadata.values import READ_FAILURES, text

SCHEMA: Final = "ridge.provenance-hints/1"
NOTICE: Final = (
    "Hints only, drawn from what the file records about itself and from how it is encoded. Ridge does not "
    "verify them, and none proves how the photo was handled. Ask for the original file from the device "
    "extraction when a copy is suspected."
)
# Long sides that messaging apps and web services commonly resize photos to (observed defaults, 2026).
COPY_SIDES: Final = frozenset({960, 1024, 1080, 1280, 1600, 2048})
# ITU-T T.81 (JPEG) Annex K, Table K.1: the luminance quantisation table the IJG quality scale starts from.
STD_LUMINANCE: Final = (
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
)  # fmt: skip
STD_LUMINANCE_SUM: Final = sum(STD_LUMINANCE)
Hint = dict[str, str]
_HEADER_FAILURES: Final[tuple[type[Exception], ...]] = (UnidentifiedImageError, *READ_FAILURES)


def _hint(ident: str, line: str) -> Hint:
    return {"id": ident, "text": text(line)}


def _header(data: bytes) -> tuple[str | None, tuple[int, int] | None, dict[int, Any] | None]:
    """Return (format, (width, height), JPEG quantisation tables) from the file header, or Nones."""
    try:
        with Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS) as im:
            tables = getattr(im, "quantization", None) if im.format == "JPEG" else None
            return im.format, (im.width, im.height), dict(tables) if isinstance(tables, dict) else None
    except _HEADER_FAILURES:
        return None, None, None


def jpeg_quality_estimate(tables: dict[int, Any] | None) -> int | None:
    """Estimate the IJG quality a JPEG was saved with from its luminance quantisation table, or None.

    The IJG scale multiplies the standard table by a factor that depends on the quality, so the sum
    of the table recovers the factor without caring about coefficient order (rounding and clipping
    make the estimate approximate; it is labelled so).
    """
    table = (tables or {}).get(0)
    if table is None or len(table) != 64:
        return None
    total = sum(int(v) for v in table)
    if total <= 0:
        return None
    scale = 100.0 * total / STD_LUMINANCE_SUM
    quality = (200.0 - scale) / 2.0 if scale <= 100.0 else 5000.0 / scale
    return int(min(100, max(1, round(quality))))


def _summary_value(meta: dict[str, Any], name: str) -> str | None:
    for entry in meta.get("summary") or []:
        if isinstance(entry, dict) and entry.get("name") == name and isinstance(entry.get("value"), str):
            return str(entry["value"])
    return None


def _exif_unreadable(meta: dict[str, Any]) -> bool:
    """Return True when the metadata reader found an EXIF block it could not parse (reported in its warnings)."""
    return any("EXIF block could not be read" in str(w) for w in meta.get("warnings") or [])


def _has_exif(meta: dict[str, Any]) -> bool:
    """Return True when an EXIF block is there, readable or not (an unreadable block is not an absent one)."""
    groups = any(str(g.get("id", "")).startswith("exif-") for g in meta.get("groups") or [] if isinstance(g, dict))
    return groups or _exif_unreadable(meta)


_HISTORY = re.compile(r"^[^:/\[]+:History(\[|$)")  # xmpMM:History under whatever prefix the packet declared


def _history_entries(meta: dict[str, Any]) -> int:
    count = 0
    for group in meta.get("groups") or []:
        if isinstance(group, dict) and group.get("id") == "xmp":
            count += sum(1 for e in group.get("entries") or [] if _HISTORY.match(str(e.get("name", ""))))
    return count


def provenance_hints(data: bytes, meta: dict[str, Any] | None) -> dict[str, Any]:
    """Build the ``ridge.provenance-hints/1`` record for a photo from its bytes and its metadata record."""
    meta = meta if isinstance(meta, dict) else {}
    fmt, size, tables = _header(data)
    hints: list[Hint] = []
    if _exif_unreadable(meta):
        hints.append(
            _hint(
                "exif-unreadable", "The EXIF block could not be read, so whether the camera's data is there is unknown."
            )
        )
    exif = _has_exif(meta)
    if not exif:
        hints.append(
            _hint(
                "no-exif",
                "The file carries no EXIF block. Camera originals almost always carry one; messaging apps, web "
                "services and many editors strip it.",
            )
        )
    elif _summary_value(meta, "Camera") is None:
        hints.append(_hint("no-camera", "The EXIF block names no camera make or model."))
    software = _summary_value(meta, "Software")
    if software:
        hints.append(
            _hint(
                "software",
                f"The file names the software '{software}'. A camera original names the phone's firmware; an "
                "editor or app name means the file was saved by it.",
            )
        )
    if size and not exif and max(size) in COPY_SIDES:
        hints.append(
            _hint(
                "copy-size",
                f"The image's longest side is {max(size)} px, a size messaging apps and web services commonly "
                "resize to; with no EXIF this is consistent with a forwarded copy.",
            )
        )
    history = _history_entries(meta)
    if history:
        hints.append(
            _hint(
                "xmp-history",
                f"The XMP edit history holds {history} recorded value(s): editing software saved the file "
                "at least once.",
            )
        )
    quality = jpeg_quality_estimate(tables) if fmt == "JPEG" else None
    if quality is not None:
        hints.append(
            _hint(
                "jpeg-quality",
                f"Estimated JPEG quality {quality} (IJG scale, from the luminance quantisation table; approximate). "
                "Phone cameras usually save at 90 or above; re-encoded copies are often lower.",
            )
        )
    if fmt == "PNG":
        hints.append(
            _hint(
                "png",
                "PNG is not a phone camera format: a PNG photo is usually a screenshot, a converted file or an "
                "edited copy.",
            )
        )
    elif fmt in ("BMP", "WEBP"):
        hints.append(
            _hint("not-camera-format", f"{fmt} is not a camera format: software converted or exported the file.")
        )
    return {"schema": SCHEMA, "hints": hints, "jpeg_quality_estimate": quality, "notice": NOTICE}


def provenance_text(section: dict[str, Any] | None) -> list[str]:
    """Text-report lines for a provenance record (empty for reports made before it)."""
    if not isinstance(section, dict):
        return []
    lines = ["Provenance    hints (not verified):"]
    lines.extend(f"              - {h.get('text')}" for h in section.get("hints") or [])
    if not section.get("hints"):
        lines.append("              - none")
    lines.append(f"              {section.get('notice', '')}")
    return lines
