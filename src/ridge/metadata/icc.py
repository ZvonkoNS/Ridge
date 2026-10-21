"""The embedded ICC colour profile: header fields and its description and copyright texts (ICC.1:2022).

Parsed by hand with bounds checks on every offset, so a hostile profile can only fail to be read;
the profile itself is summarised by size and SHA-256.
"""

from __future__ import annotations

import struct

from ridge.metadata.values import Budget, binary

MAX_TAGS = 100  # profiles have about 10-30 tags
MAX_TEXT_BYTES = 4096
_CLASSES = {
    b"scnr": "input device",
    b"mntr": "display device",
    b"prtr": "output device",
    b"link": "device link",
    b"spac": "colour space",
    b"abst": "abstract",
    b"nmcl": "named colour",
}
_TEXT_TAGS = {b"desc": "Description", b"cprt": "Copyright", b"dmnd": "Device manufacturer", b"dmdd": "Device model"}


def _sig(data: bytes, at: int) -> str:
    value = data[at : at + 4]
    return value.decode("latin-1").strip("\x00 ") if value.strip(b"\x00 ") else "none"


def _date(data: bytes) -> str | None:
    year, month, day, hour, minute, second = struct.unpack_from(">6H", data, 24)
    if year == 0:
        return None
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


def _text(data: bytes, offset: int, size: int) -> str | None:
    """Read a desc (v2), mluc (v4) or text tag; None when it is malformed."""
    if offset < 0 or size < 12 or offset + size > len(data):
        return None
    body = data[offset : offset + min(size, MAX_TEXT_BYTES)]
    kind = body[:4]
    if kind == b"text":
        return body[8:].split(b"\x00", 1)[0].decode("latin-1")
    if kind == b"desc":
        (count,) = struct.unpack_from(">I", body, 8)
        return body[12 : 12 + count].split(b"\x00", 1)[0].decode("latin-1")
    if kind == b"mluc" and len(body) >= 28:
        records, record_size = struct.unpack_from(">II", body, 8)
        if records < 1 or record_size < 12:
            return None
        length, start = struct.unpack_from(">II", body, 20)  # the first record (usually en-US)
        return body[start : start + length].decode("utf-16-be", "replace")
    return None


def read_icc(profile: bytes, budget: Budget) -> list[dict[str, str]]:
    """Entries describing an ICC profile; an unparseable profile gives its size and hash only."""
    entries = [budget.entry("Profile", binary(profile, "ICC profile"))]
    if len(profile) < 132 or profile[36:40] != b"acsp":
        entries.append(budget.entry("Note", "not a valid ICC profile header; not decoded"))
        return [e for e in entries if e is not None]
    major, minor = profile[8], profile[9] >> 4
    fields = [
        ("Version", f"{major}.{minor}"),
        ("Class", _CLASSES.get(profile[12:16], _sig(profile, 12))),
        ("Colour space", _sig(profile, 16)),
        ("Connection space", _sig(profile, 20)),
        ("Created", _date(profile) or "not recorded"),
        ("Preferred CMM", _sig(profile, 4)),
        ("Platform", _sig(profile, 40)),
        ("Device manufacturer code", _sig(profile, 48)),
        ("Device model code", _sig(profile, 52)),
        ("Creator", _sig(profile, 80)),
        ("Profile ID", profile[84:100].hex() if profile[84:100].strip(b"\x00") else "not recorded"),
    ]
    (count,) = struct.unpack_from(">I", profile, 128)
    for i in range(min(count, MAX_TAGS)):
        at = 132 + 12 * i
        if at + 12 > len(profile):
            break
        signature = profile[at : at + 4]
        offset, size = struct.unpack_from(">II", profile, at + 4)
        if signature in _TEXT_TAGS and (shown := _text(profile, offset, size)) is not None:
            fields.append((_TEXT_TAGS[signature], shown))
    fields.append(("Tags", f"{count}" + (f" (the first {MAX_TAGS} read)" if count > MAX_TAGS else "")))
    entries.extend(budget.entry(name, value) for name, value in fields)
    return [e for e in entries if e is not None]
