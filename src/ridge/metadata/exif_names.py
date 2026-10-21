"""Words for EXIF codes (CIPA DC-008 / EXIF 2.32 and 3.0), so the examiner does not have to look them up.

A labelled value is shown as recorded with its meaning, for example ``6 (rotate 90 CW)``. Codes
outside the tables are shown as recorded. Nothing here interprets or judges the values.
"""

from __future__ import annotations

from typing import Any

from ridge.metadata.values import as_text, binary

GPS_LABELS: dict[int, dict[Any, str]] = {
    5: {0: "above sea level", 1: "below sea level", 2: "above sea level (ellipsoid)", 3: "below sea level (ellipsoid)"},
    9: {"A": "measurement in progress", "V": "measurement interrupted"},
    10: {"2": "2-dimensional", "3": "3-dimensional"},
    12: {"K": "km/h", "M": "mph", "N": "knots"},
    14: {"T": "true north", "M": "magnetic north"},
    16: {"T": "true north", "M": "magnetic north"},
    23: {"T": "true north", "M": "magnetic north"},
    25: {"K": "kilometres", "M": "miles", "N": "nautical miles"},
    30: {0: "without differential correction", 1: "differential correction applied"},
}

LABELS: dict[int, dict[Any, str]] = {
    0x0103: {1: "uncompressed", 5: "LZW", 6: "JPEG (old-style)", 7: "JPEG", 8: "Deflate", 32773: "PackBits"},
    0x0106: {0: "white is zero", 1: "black is zero", 2: "RGB", 3: "palette", 5: "CMYK", 6: "YCbCr"},
    0x0112: {
        1: "normal",
        2: "mirror horizontal",
        3: "rotate 180",
        4: "mirror vertical",
        5: "mirror horizontal and rotate 270 CW",
        6: "rotate 90 CW",
        7: "mirror horizontal and rotate 90 CW",
        8: "rotate 270 CW",
    },
    0x0128: {1: "no unit", 2: "inches", 3: "centimetres"},
    0x0213: {1: "centred", 2: "co-sited"},
    0x8822: {
        0: "not defined",
        1: "manual",
        2: "normal program",
        3: "aperture priority",
        4: "shutter priority",
        5: "creative program",
        6: "action program",
        7: "portrait mode",
        8: "landscape mode",
    },
    0x8830: {
        0: "unknown",
        1: "standard output sensitivity",
        2: "recommended exposure index",
        3: "ISO speed",
        4: "SOS and REI",
        5: "SOS and ISO speed",
        6: "REI and ISO speed",
        7: "SOS, REI and ISO speed",
    },
    0x9207: {
        0: "unknown",
        1: "average",
        2: "centre-weighted average",
        3: "spot",
        4: "multi-spot",
        5: "pattern",
        6: "partial",
        255: "other",
    },
    0x9208: {
        0: "unknown",
        1: "daylight",
        2: "fluorescent",
        3: "tungsten",
        4: "flash",
        9: "fine weather",
        10: "cloudy",
        11: "shade",
        12: "daylight fluorescent",
        13: "day white fluorescent",
        14: "cool white fluorescent",
        15: "white fluorescent",
        16: "warm white fluorescent",
        17: "standard light A",
        18: "standard light B",
        19: "standard light C",
        20: "D55",
        21: "D65",
        22: "D75",
        23: "D50",
        24: "ISO studio tungsten",
        255: "other",
    },
    0xA001: {1: "sRGB", 0xFFFF: "uncalibrated"},
    0xA210: {1: "no unit", 2: "inches", 3: "centimetres"},
    0xA217: {
        1: "not defined",
        2: "one-chip colour area sensor",
        3: "two-chip colour area sensor",
        4: "three-chip colour area sensor",
        5: "colour sequential area sensor",
        7: "trilinear sensor",
        8: "colour sequential linear sensor",
    },
    0xA401: {0: "normal process", 1: "custom process"},
    0xA402: {0: "auto exposure", 1: "manual exposure", 2: "auto bracket"},
    0xA403: {0: "auto", 1: "manual"},
    0xA406: {0: "standard", 1: "landscape", 2: "portrait", 3: "night scene"},
    0xA407: {0: "none", 1: "low gain up", 2: "high gain up", 3: "low gain down", 4: "high gain down"},
    0xA408: {0: "normal", 1: "soft", 2: "hard"},
    0xA409: {0: "normal", 1: "low", 2: "high"},
    0xA40A: {0: "normal", 1: "soft", 2: "hard"},
    0xA40C: {0: "unknown", 1: "macro", 2: "close view", 3: "distant view"},
}

_BYTE_CODES: dict[int, dict[Any, str]] = {  # FileSource and SceneType: one UNDEFINED byte each
    0xA300: {1: "film scanner", 2: "reflection print scanner", 3: "digital still camera"},
    0xA301: {1: "directly photographed"},
}
_COMPONENTS = {0: "-", 1: "Y", 2: "Cb", 3: "Cr", 4: "R", 5: "G", 6: "B"}
_FLASH_RETURN = {0: "", 2: "return light not detected", 3: "return light detected"}
_FLASH_MODE = {0: "", 1: "compulsory flash firing", 2: "compulsory flash suppression", 3: "auto mode"}
_VERSIONS = {0x9000, 0xA000, 0x0002}  # ExifVersion, FlashpixVersion, InteropVersion: four ASCII digits
_CHARSETS = {b"ASCII\x00\x00\x00": "ascii", b"UNICODE\x00": "unicode", b"JIS\x00\x00\x00\x00\x00": "jis"}


def label(table: dict[Any, str] | None, value: Any, shown: str) -> str:
    """Append the meaning of a coded value, when the table knows it."""
    key = value.rstrip("\x00") if isinstance(value, str) else value
    if isinstance(key, bytes) and len(key) == 1:
        key = key[0]
    meaning = table.get(key) if table is not None and isinstance(key, int | str) else None
    return f"{shown} ({meaning})" if meaning else shown


def flash(value: int) -> str:
    """Put the Flash bit field in words (EXIF 2.32, 4.6.5)."""
    if value & 0x20:
        return f"{value} (no flash function)"
    parts = [
        "fired" if value & 1 else "did not fire",
        _FLASH_RETURN.get((value >> 1) & 3, ""),
        _FLASH_MODE[(value >> 3) & 3],
    ]
    if value & 0x40:
        parts.append("red-eye reduction")
    return f"{value} ({', '.join(p for p in parts if p)})"


def comment(data: bytes, big_endian: bool) -> str:
    """Decode a UserComment or GPS processing method: an 8-byte character-set code, then the text."""
    charset = _CHARSETS.get(data[:8])
    body = data[8:]
    if charset == "ascii":  # writers often put UTF-8 here; anything else is read as Latin-1
        stripped = body.rstrip(b"\x00")
        try:
            return stripped.decode("utf-8")
        except UnicodeDecodeError:
            return stripped.decode("latin-1")
    if charset == "unicode":
        if len(body) % 2:
            body = body[:-1]
        return body.decode("utf-16-be" if big_endian else "utf-16-le", "replace").rstrip("\x00")
    if data[:8] == b"\x00" * 8 and not body.strip(b"\x00 "):
        return "empty"
    shown = as_text(body) if charset is None and data[:8] == b"\x00" * 8 else None
    if shown is not None:
        return shown
    return binary(data, "text in an undeclared or JIS character set" if charset else "binary data")


def _four_bytes(tag: int, value: bytes) -> str | None:
    """Versions ("0232") and the component order (1 2 3 0 is Y Cb Cr)."""
    if len(value) != 4:
        return None
    if tag in _VERSIONS and value.isdigit():
        return f"{value.decode()} (version {int(value[:2])}.{value[2:].decode()})"
    if tag == 0x9101:
        return " ".join(_COMPONENTS.get(b, f"?{b}") for b in value)
    return None


def special(tag: int, value: Any, big_endian: bool) -> str | None:
    """Put EXIF values whose raw form says little (versions, components, comments) in words, else None."""
    if not isinstance(value, bytes):
        return flash(value) if tag == 0x9209 and isinstance(value, int) else None
    if tag == 0x9286:
        return comment(value, big_endian)
    if tag in _BYTE_CODES and len(value) == 1:
        return label(_BYTE_CODES[tag], value[0], str(value[0]))
    return _four_bytes(tag, value)
