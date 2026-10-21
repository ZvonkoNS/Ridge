"""IPTC-IIM metadata (records 1 and 2, IPTC IIM 4.2) from JPEG Photoshop blocks and TIFF tag 33723."""

from __future__ import annotations

from typing import Any

from PIL import ImageFile, IptcImagePlugin

from ridge.metadata.values import Budget, binary, items

NAMES: dict[tuple[int, int], str] = {
    (1, 0): "Envelope record version",
    (1, 5): "Destination",
    (1, 20): "File format",
    (1, 22): "File format version",
    (1, 30): "Service identifier",
    (1, 40): "Envelope number",
    (1, 50): "Product ID",
    (1, 60): "Envelope priority",
    (1, 70): "Date sent",
    (1, 80): "Time sent",
    (1, 90): "Coded character set",
    (1, 100): "Unique name of object",
    (2, 0): "Record version",
    (2, 3): "Object type reference",
    (2, 4): "Object attribute reference",
    (2, 5): "Object name",
    (2, 7): "Edit status",
    (2, 10): "Urgency",
    (2, 12): "Subject reference",
    (2, 15): "Category",
    (2, 20): "Supplemental category",
    (2, 22): "Fixture identifier",
    (2, 25): "Keywords",
    (2, 26): "Content location code",
    (2, 27): "Content location name",
    (2, 30): "Release date",
    (2, 35): "Release time",
    (2, 37): "Expiration date",
    (2, 38): "Expiration time",
    (2, 40): "Special instructions",
    (2, 42): "Action advised",
    (2, 45): "Reference service",
    (2, 47): "Reference date",
    (2, 50): "Reference number",
    (2, 55): "Date created",
    (2, 60): "Time created",
    (2, 62): "Digital creation date",
    (2, 63): "Digital creation time",
    (2, 65): "Originating program",
    (2, 70): "Program version",
    (2, 75): "Object cycle",
    (2, 80): "By-line (creator)",
    (2, 85): "By-line title",
    (2, 90): "City",
    (2, 92): "Sub-location",
    (2, 95): "Province or state",
    (2, 100): "Country code",
    (2, 101): "Country name",
    (2, 103): "Original transmission reference",
    (2, 105): "Headline",
    (2, 110): "Credit",
    (2, 115): "Source",
    (2, 116): "Copyright notice",
    (2, 118): "Contact",
    (2, 120): "Caption or abstract",
    (2, 122): "Writer or editor",
    (2, 130): "Image type",
    (2, 131): "Image orientation",
    (2, 135): "Language identifier",
}
UTF8_MARK = b"\x1b%G"  # dataset 1:90 for UTF-8


def _decode(value: bytes, utf8: bool) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return binary(value) if utf8 else value.decode("latin-1")


def read_iptc(im: ImageFile.ImageFile, budget: Budget) -> list[dict[str, str]]:
    """Entries for the image's IPTC datasets, in record and dataset order (Pillow parses the block)."""
    info: dict[tuple[int, int], Any] | None = IptcImagePlugin.getiptcinfo(im)
    if not info:
        return []
    utf8 = info.get((1, 90)) == UTF8_MARK
    entries = []
    for key in sorted(info):
        raw = info[key]
        values = raw if isinstance(raw, list) else [raw]
        shown = items(_decode(v, utf8) if isinstance(v, bytes) else str(v) for v in values)
        name = NAMES.get(key, f"Dataset {key[0]}:{key[1]}")
        entries.append(budget.entry(name, shown, f"{key[0]}:{key[1]}"))
    return [e for e in entries if e is not None]
