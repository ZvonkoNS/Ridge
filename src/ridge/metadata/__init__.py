"""Metadata of an imported photo, read from its exact bytes (PRD FR-36, architecture §8.3).

`read_metadata` is pure: bytes in, a bounded, JSON-ready dict out (schema ``ridge.photo-metadata/1``).
Ridge reads it from the verified copy in the case store: the original file is not opened for
this and never changed, and no metadata is ever copied into an output image (FR-12). Values are
shown as recorded, made safe to display, and never interpreted: Ridge does not verify metadata.
"""

from __future__ import annotations

import io
import warnings
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageFile, UnidentifiedImageError

from ridge.errors import DecodeError, InputRejectedError
from ridge.image_io import ALLOWED_FORMATS
from ridge.metadata.containers import XMP_PNG_KEY, file_facts, heif_items, jpeg_structure, png_text
from ridge.metadata.exif import read_exif
from ridge.metadata.gps import compare, exif_location, xmp_location
from ridge.metadata.icc import read_icc
from ridge.metadata.iptc import read_iptc
from ridge.metadata.summary import summary
from ridge.metadata.values import MAX_ENTRIES, MAX_TOTAL_BYTES, READ_FAILURES, Budget, text
from ridge.metadata.xmp import XmpRead, read_xmp

SCHEMA = "ridge.photo-metadata/1"
NOTICE = (
    "Read from the file as stored. Ridge does not verify metadata: any editor can change or remove it, "
    "so it does not by itself establish where, when or with what the photo was taken."
)
Entries = list[dict[str, str]]


def _xmp_packet(im: Image.Image) -> bytes | None:
    for key in ("xmp", XMP_PNG_KEY):
        value = im.info.get(key)
        if isinstance(value, bytes | str) and value:
            return value if isinstance(value, bytes) else value.encode("utf-8")
    tags = getattr(im, "tag_v2", None)
    value = tags.get(700) if tags is not None else None  # TIFF XMLPacket
    return value if isinstance(value, bytes) and value else None


def _safely(title: str, read: Callable[[], Entries], warnings_out: list[str]) -> Entries:
    """Read one group; a malformed group is reported as unreadable instead of stopping the others."""
    try:
        return read()
    except READ_FAILURES as exc:
        warnings_out.append(f"{title} could not be read ({type(exc).__name__}).")
        return []


def _locate(gps: dict[int, Any], xmp: XmpRead, out: list[str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return the EXIF and XMP positions; a position that cannot be converted is a warning, never fatal."""
    try:
        found = exif_location(gps, out)
        from_xmp = xmp_location(xmp.gps_latitude, xmp.gps_longitude, out)
    except READ_FAILURES as exc:
        out.append(f"The GPS position could not be read ({type(exc).__name__}); the raw tags are listed.")
        return None, None
    compare(found, from_xmp, out)
    return found, from_xmp


def _group(ident: str, title: str, entries: Entries) -> dict[str, Any]:
    return {"id": ident, "title": title, "entries": entries}


def _read(im: ImageFile.ImageFile, data: bytes, budget: Budget, fixed: Budget, out: list[str]) -> dict[str, Any]:
    groups = [_group("file", "File", _safely("File facts", lambda: file_facts(im, data, fixed), out))]
    exif = read_exif(im, budget, out)
    groups.extend(exif.groups)
    xmp = XmpRead()
    packet = _xmp_packet(im)
    if packet is not None:
        xmp = read_xmp(packet, budget, out)
        groups.append(_group("xmp", "XMP", xmp.entries))
    if im.format in ("JPEG", "MPO", "TIFF"):
        groups.append(_group("iptc", "IPTC", _safely("IPTC", lambda: read_iptc(im, budget), out)))
    icc = im.info.get("icc_profile")
    if isinstance(icc, bytes) and icc:
        groups.append(_group("icc", "ICC profile", _safely("The ICC profile", lambda: read_icc(icc, budget), out)))
    if im.format in ("JPEG", "MPO"):
        groups.append(
            _group("jpeg", "JPEG structure", _safely("JPEG structure", lambda: jpeg_structure(im, budget), out))
        )
    if im.format == "PNG":
        groups.append(_group("png-text", "PNG text", _safely("PNG text", lambda: png_text(im, budget, out), out)))
    if im.format == "HEIF":
        groups.append(_group("heif", "HEIF", _safely("HEIF items", lambda: heif_items(im, budget), out)))
    if 0x927C in exif.tags:
        out.append(
            "The camera maker's MakerNote is vendor-specific and was not decoded; its size and SHA-256 are listed."
        )
    found, from_xmp = _locate(exif.gps, xmp, out)
    return {
        "schema": SCHEMA,
        "notice": NOTICE,
        "summary": summary(exif.tags, xmp.creator_tool, fixed),
        "location": found or from_xmp,
        "groups": [g for g in groups if g["entries"]],
        "embedded": exif.embedded,
    }


def _open(data: bytes) -> ImageFile.ImageFile:
    """Open (not decode) an allow-listed image, with the typed errors decoding gives."""
    try:
        return Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS)
    except UnidentifiedImageError as exc:
        raise InputRejectedError("not a supported image") from exc
    except Image.DecompressionBombError as exc:
        raise InputRejectedError("image dimensions exceed the decoder's safety limit") from exc
    except READ_FAILURES as exc:
        raise DecodeError("image header is corrupt or truncated") from exc


def read_metadata(data: bytes) -> dict[str, Any]:
    """Every metadata block Ridge can read from an allow-listed image, bounded and display-safe.

    Raises InputRejectedError (not an allow-listed image) or DecodeError (a corrupt header) when the
    image cannot be opened, as decoding would. Once it is open, a malformed metadata block is
    reported in ``warnings`` and never stops the others; any other exception is a bug and propagates.
    """
    budget, fixed = Budget(), Budget()  # `fixed` holds the file facts and the summary, always kept
    out: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)  # Ridge's own limits applied at import
        with _open(data) as im:
            found = _read(im, data, budget, fixed, out)
    out.extend(f"The image library reported: {text(str(w.message))[:300]}" for w in caught)
    if budget.dropped:
        out.append(
            f"{budget.dropped} entries were left out to keep the record bounded "
            f"(at most {MAX_ENTRIES} entries and {MAX_TOTAL_BYTES // 1000} kB of text)."
        )
    if budget.shortened + fixed.shortened:
        out.append(f"{budget.shortened + fixed.shortened} long values were shortened.")
    found["warnings"] = list(dict.fromkeys(out))  # in order, each once
    found["entries"] = budget.entries + fixed.entries
    found["truncated"] = budget.dropped > 0
    return found


__all__ = ["NOTICE", "SCHEMA", "read_metadata"]
