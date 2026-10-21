"""Facts about the file itself and format-specific blocks: JPEG segments and MPF, PNG text, HEIF items.

None of these read pixels, except that PNG text stored after the image data needs the image
decoded; that is done only within Ridge's pixel limit (the photo was decoded at import anyway).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from PIL import Image

from ridge.image_io import DEFAULT_MAX_PIXELS
from ridge.metadata.values import Budget, describe, items, sha256

XMP_PNG_KEY = "XML:com.adobe.xmp"  # PNG iTXt keyword of an XMP packet (shown in the XMP group)
_IDENT = re.compile(rb"[\x20-\x7e]{2,40}")
_BITS = {"1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8, "CMYK": 8, "YCbCr": 8, "LA": 8, "I;16": 16, "I": 32, "F": 32}


def _dpi(value: Any) -> str | None:
    if isinstance(value, tuple) and len(value) == 2:
        return f"{describe(value[0])} x {describe(value[1])} dpi (declared in the file, not a measured scale)"
    return None


def file_facts(im: Image.Image, data: bytes, budget: Budget) -> list[dict[str, str]]:
    """Format, size, hash, pixel layout and declared resolution of the file as stored."""
    frames = int(getattr(im, "n_frames", 1) or 1)
    info = im.info
    bits = info.get("bit_depth", _BITS.get(im.mode))
    facts: list[tuple[str, str | None]] = [
        ("Format", f"{im.format} ({Image.MIME.get(im.format or '', 'unknown type')})"),
        ("File size", f"{len(data):,} bytes"),
        ("SHA-256", sha256(data)),
        ("Stored size", f"{im.width} x {im.height} px (before EXIF orientation)"),
        ("Colour mode", im.mode),
        ("Bits per sample", None if bits is None else str(bits)),
        ("Images in the file", None if frames == 1 else f"{frames} (Ridge processes the first)"),
        ("Resolution", _dpi(info.get("dpi"))),
        ("Progressive", "yes" if info.get("progressive") or info.get("progression") else None),
        ("Interlaced", "yes" if info.get("interlace") else None),
        ("Compression", describe(info["compression"]) if "compression" in info else None),
        ("JFIF version", ".".join(str(v) for v in info["jfif_version"]) if "jfif_version" in info else None),
        ("Adobe colour transform", describe(info["adobe_transform"]) if "adobe_transform" in info else None),
        ("Gamma", describe(info["gamma"]) if "gamma" in info else None),
        ("sRGB rendering intent", describe(info["srgb"]) if "srgb" in info else None),
        ("ICC profile", "embedded (see ICC profile)" if info.get("icc_profile") else None),
    ]
    entries = (budget.entry(name, value) for name, value in facts if value is not None)
    return [e for e in entries if e is not None]


def _ident(data: bytes) -> str:
    found = _IDENT.match(data.split(b"\x00", 1)[0])
    return found.group().decode("ascii") if found else "no identifier"


def jpeg_structure(im: Image.Image, budget: Budget) -> list[dict[str, str]]:
    """List the JPEG's APPn and COM segments in file order, and the images an MPF index lists."""
    entries = []
    for marker, payload in getattr(im, "applist", []):
        if marker == "COM":
            entries.append(budget.entry("Comment (COM)", describe(payload)))
        else:
            entries.append(budget.entry(marker, f"{_ident(payload)}, {len(payload):,} bytes"))
    mpinfo = im.info.get("mpinfo")
    listed = mpinfo.get(0xB002) if isinstance(mpinfo, dict) else None
    for i, entry in enumerate(listed if isinstance(listed, list) else [], start=1):
        attribute = entry.get("Attribute", {}) if isinstance(entry, dict) else {}
        kind = attribute.get("MPType", "unknown type") if isinstance(attribute, dict) else "unknown type"
        size = entry.get("Size") if isinstance(entry, dict) else None
        entries.append(budget.entry(f"MPF image {i}", f"{describe(kind)}, {describe(size)} bytes"))
    return [e for e in entries if e is not None]


def png_text(im: Image.Image, budget: Budget, warnings: list[str]) -> list[dict[str, str]]:
    """PNG tEXt, zTXt and iTXt chunks (the XMP packet is shown in its own group)."""
    if im.width * im.height > DEFAULT_MAX_PIXELS:
        warnings.append("Text chunks after the image data were not read: the image is above Ridge's pixel limit.")
        chunks = {str(k): v for k, v in im.info.items() if isinstance(v, str)}
    else:
        chunks = dict(getattr(im, "text", {}))  # Pillow reads chunks after IDAT by loading the image
    entries = (budget.entry(key, describe(value)) for key, value in chunks.items() if key != XMP_PNG_KEY)
    return [e for e in entries if e is not None]


def heif_items(im: Image.Image, budget: Budget) -> list[dict[str, str]]:
    """Say what else a HEIF file holds besides the primary image (counts and kinds only)."""
    info = im.info
    counted: list[tuple[str, Callable[[Any], str | None]]] = [
        ("primary", lambda v: "yes" if v else "no"),
        ("chroma", lambda v: f"4:{str(v)[1]}:{str(v)[2]}" if isinstance(v, int) and len(str(v)) == 3 else str(v)),
        ("thumbnails", lambda v: str(len(v)) if isinstance(v, list | tuple) else None),
        ("depth_images", lambda v: str(len(v)) if isinstance(v, list | tuple) else None),
        ("aux", lambda v: items(str(k) for k in v) if isinstance(v, dict) and v else None),
        ("metadata", lambda v: items(str(m.get("type", "?")) for m in v if isinstance(m, dict)) if v else None),
    ]
    names = {
        "primary": "Primary image",
        "chroma": "Chroma subsampling",
        "thumbnails": "Thumbnails",
        "depth_images": "Depth images",
        "aux": "Auxiliary images",
        "metadata": "Other metadata blocks",
    }
    entries = []
    for key, show in counted:
        if key in info and (value := show(info[key])) is not None:
            entries.append(budget.entry(names[key], value))
    return [e for e in entries if e is not None]
