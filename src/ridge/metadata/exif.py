"""EXIF groups: every tag of IFD0, the Exif, GPS and interoperability IFDs and the thumbnail IFD (IFD1).

Tags are listed in file order with their number, name and value. Links to other IFDs are left
out (they are structure, not values). Blocks that other groups show in full (XMP, IPTC, ICC) and
the vendor-specific MakerNote are summarised by size and SHA-256. The embedded thumbnail is an
image of the photo: Ridge records its size and hash, never its pixels.
"""

from __future__ import annotations

import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from PIL import ExifTags, Image

from ridge.metadata.exif_names import GPS_LABELS, LABELS, comment, label, special
from ridge.metadata.values import READ_FAILURES, Budget, binary, describe, sha256

POINTERS = frozenset({0x8769, 0x8825, 0xA005})  # Exif, GPS and interoperability IFD offsets
ELSEWHERE = {0x02BC: "XMP packet (see XMP)", 0x83BB: "IPTC data (see IPTC)", 0x8773: "ICC profile (see ICC profile)"}
GPS_TEXT = frozenset({27, 28})  # GPSProcessingMethod, GPSAreaInformation: character-set code, then text
_GROUPS: tuple[tuple[str, str, int | None], ...] = (
    ("exif-ifd0", "EXIF: image (IFD0)", None),
    ("exif-photo", "EXIF: photo", ExifTags.IFD.Exif),
    ("exif-gps", "EXIF: GPS", ExifTags.IFD.GPSInfo),
    ("exif-interop", "EXIF: interoperability", ExifTags.IFD.Interop),
    ("exif-ifd1", "EXIF: thumbnail (IFD1)", ExifTags.IFD.IFD1),
)
_VENDOR = re.compile(rb"[A-Za-z][A-Za-z0-9 ]{2,15}")


@dataclass
class ExifRead:
    """The EXIF groups, plus the raw tags the summary, the location and the thumbnail need."""

    groups: list[dict[str, Any]] = field(default_factory=list)
    tags: dict[int, Any] = field(default_factory=dict)  # IFD0 and Exif IFD
    gps: dict[int, Any] = field(default_factory=dict)
    embedded: list[dict[str, Any]] = field(default_factory=list)


def tag_name(tag: int, gps: bool = False) -> str:
    """Return the EXIF name of a tag, or its number when Pillow does not know it."""
    name = (ExifTags.GPSTAGS if gps else ExifTags.TAGS).get(tag)
    return name or f"Tag 0x{tag:04X}"


def makernote(value: Any) -> str:
    """Summarise a MakerNote: vendor-specific binary data that Ridge does not decode."""
    data = value if isinstance(value, bytes) else str(value).encode("utf-8", "replace")
    vendor = _VENDOR.match(data[:16])
    origin = f" starting {vendor.group().decode('ascii')!r}" if vendor else ""
    return binary(data, f"vendor-specific data{origin}, not decoded")


def value_text(tag: int, value: Any, *, gps: bool, big_endian: bool) -> str:
    """One tag's value in words where EXIF defines them, else as recorded."""
    if not gps and tag in ELSEWHERE:
        size = len(value) if isinstance(value, bytes | str | tuple) else 0
        return f"{ELSEWHERE[tag]}, {size:,} bytes"
    if not gps and tag == 0x927C:
        return makernote(value)
    if gps and tag in GPS_TEXT and isinstance(value, bytes):
        return comment(value, big_endian)
    if gps and tag == 0 and isinstance(value, bytes | tuple) and len(value) == 4:
        return ".".join(str(v) for v in value)
    shown = None if gps else special(tag, value, big_endian)
    if shown is not None:
        return shown
    return label((GPS_LABELS if gps else LABELS).get(tag), value, describe(value))


def read_exif(im: Image.Image, budget: Budget, warnings: list[str]) -> ExifRead:
    """Read every EXIF group of an opened image (an unreadable group is reported, not fatal)."""
    found = ExifRead()
    try:
        exif = im.getexif()
    except READ_FAILURES as exc:
        warnings.append(f"The EXIF block could not be read ({type(exc).__name__}).")
        return found
    big_endian = exif.endian == ">"
    for ident, title, ifd in _GROUPS:
        if ifd == ExifTags.IFD.Interop and 0xA005 not in found.tags:
            continue  # Pillow finds this IFD through the Exif IFD's pointer, which is absent
        try:
            tags: Mapping[int, Any] = exif if ifd is None else exif.get_ifd(ifd)
            pairs = [(int(t), v) for t, v in tags.items()]
        except READ_FAILURES as exc:
            warnings.append(f"{title} could not be read ({type(exc).__name__}).")
            continue
        is_gps = ifd == ExifTags.IFD.GPSInfo
        if ifd in (None, ExifTags.IFD.Exif):
            found.tags.update(pairs)
        if is_gps:
            found.gps = dict(pairs)
        entries = [
            budget.entry(
                tag_name(tag, is_gps), value_text(tag, value, gps=is_gps, big_endian=big_endian), f"0x{tag:04X}"
            )
            for tag, value in pairs
            if is_gps or tag not in POINTERS
        ]
        kept = [e for e in entries if e is not None]
        if kept:
            found.groups.append({"id": ident, "title": title, "entries": kept})
        if ifd == ExifTags.IFD.IFD1:
            found.embedded.extend(_thumbnail(im, dict(pairs)))
    return found


def _thumbnail(im: Image.Image, ifd1: dict[int, Any]) -> list[dict[str, Any]]:
    """Describe the JPEG thumbnail IFD1 points to: its size, hash and pixel size, never its pixels."""
    offset, length = ifd1.get(0x0201), ifd1.get(0x0202)
    raw = im.info.get("exif")
    if not isinstance(offset, int) or not isinstance(length, int) or not isinstance(raw, bytes) or length <= 0:
        return []
    tiff = raw[6:] if raw.startswith(b"Exif\x00\x00") else raw  # offsets count from the TIFF header
    if offset < 0 or offset + length > len(tiff):
        return [{"kind": "EXIF thumbnail", "note": "its offset or length points outside the EXIF block"}]
    data = tiff[offset : offset + length]
    found: dict[str, Any] = {"kind": "EXIF thumbnail", "bytes": len(data), "sha256": sha256(data)}
    try:
        with Image.open(io.BytesIO(data), formats=("JPEG",)) as thumb:  # header only; pixels never decoded
            found.update(format="JPEG", size_px=[thumb.width, thumb.height])
    except READ_FAILURES:
        found["note"] = "not a readable JPEG"
    return [found]
