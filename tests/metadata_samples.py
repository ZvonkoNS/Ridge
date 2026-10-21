"""Synthetic images carrying metadata, made in memory (no real photo, nothing written to the repository).

Pillow writes the ordinary blocks (EXIF with GPS, XMP, ICC, PNG text). Blocks Pillow cannot
write are assembled by hand: a raw EXIF block with a thumbnail IFD, and an IPTC block in a JPEG
APP13 Photoshop segment.
"""

from __future__ import annotations

import io
import struct
from typing import Any

import numpy as np
from PIL import ExifTags, Image, ImageCms, PngImagePlugin
from PIL.TiffImagePlugin import IFDRational

from tests.golden_cases import CASES_BY_NAME

R = IFDRational
XMP_NS = (
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:exif="http://ns.adobe.com/exif/1.0/" '
    'xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/" xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"'
)
LAT = (R(46, 1), R(3, 1), R(444, 100))  # 46 deg 3' 4.44" = 46.0512333...
LON = (R(14, 1), R(30, 1), R(2044, 100))  # 14 deg 30' 20.44" = 14.5056778...
MAP_URL = "https://www.google.com/maps/search/?api=1&query=46.0512333%2C14.5056778"


def xmp(body: str = "", attrs: str = 'xmp:CreatorTool="Synthetic Editor 3"') -> bytes:
    """An XMP packet with one rdf:Description holding `attrs` and `body`."""
    return (
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
        f"<rdf:RDF {XMP_NS}><rdf:Description {attrs}>{body}</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode()


HISTORY = (
    "<dc:subject><rdf:Bag><rdf:li>finger</rdf:li><rdf:li>test</rdf:li></rdf:Bag></dc:subject>"
    '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">Title</rdf:li><rdf:li xml:lang="sl">Naslov</rdf:li></rdf:Alt>'
    "</dc:title><xmpMM:History><rdf:Seq>"
    '<rdf:li rdf:parseType="Resource"><stEvt:action>saved</stEvt:action>'
    "<stEvt:softwareAgent>Synthetic Editor 3</stEvt:softwareAgent></rdf:li>"
    "</rdf:Seq></xmpMM:History>"
)


def gps_ifd(exif: Image.Exif, **overrides: Any) -> None:
    """Fill the GPS IFD with a valid synthetic position; `overrides` replace tags by number (t2=...), None removes."""
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    values: dict[int, Any] = {
        0: b"\x02\x03\x00\x00",
        1: "N",
        2: LAT,
        3: "E",
        4: LON,
        5: b"\x00",
        6: R(2953, 10),
        7: (R(8, 1), R(22, 1), R(335, 10)),
        18: "WGS-84",
        29: "2024:05:01",
    }
    for key, value in overrides.items():
        tag = int(key[1:])
        if value is None:
            values.pop(tag, None)
        else:
            values[tag] = value
    gps.update(values)


def camera_exif(orientation: int = 6, **gps: Any) -> Image.Exif:
    """EXIF with camera, time, exposure, MakerNote and GPS tags (all synthetic)."""
    exif = Image.Exif()
    exif.update({0x010F: "Synthetic Camera Co", 0x0110: "Model 7", 0x0131: "Firmware 1.2", 0x0112: orientation})
    exif.get_ifd(ExifTags.IFD.Exif).update(
        {
            0x9000: b"0232",
            0x9003: "2024:05:01 10:22:33",
            0x9011: "+02:00",
            0x9291: "123",
            0x829A: R(1, 120),
            0x829D: R(18, 10),
            0x8827: 100,
            0x920A: R(42, 10),
            0xA405: 26,
            0x9209: 16,
            0x9286: b"ASCII\x00\x00\x00synthetic comment",
            0x927C: b"SynthMaker\x00\x01\x02\x03" + bytes(range(40)),
            0xA431: "SN-0001",
        }
    )
    gps_ifd(exif, **gps)
    return exif


def icc_profile() -> bytes:
    """A small sRGB profile made by LittleCMS."""
    return bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())


def small_image() -> Image.Image:
    rng = np.random.default_rng(5)
    return Image.fromarray(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8))


def jpeg(exif: Image.Exif | bytes | None = None, *, xmp_packet: bytes | None = None, icc: bool = True) -> bytes:
    """A JPEG with the given EXIF, XMP, an ICC profile and a comment."""
    buf = io.BytesIO()
    extra: dict[str, Any] = {"comment": b"synthetic comment segment"}
    if exif is not None:
        extra["exif"] = exif
    if xmp_packet is not None:
        extra["xmp"] = xmp_packet
    if icc:
        extra["icc_profile"] = icc_profile()
    small_image().save(buf, "JPEG", **extra)
    return buf.getvalue()


def full_jpeg() -> bytes:
    """The richest sample: camera EXIF with GPS, XMP with an edit history, ICC profile, comment."""
    return jpeg(camera_exif(), xmp_packet=xmp(HISTORY))


def thumbnail_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 12), (90, 90, 90)).save(buf, "JPEG")
    return buf.getvalue()


def _ifd(entries: list[tuple[int, int, int, bytes]], next_ifd: int, data_at: int) -> tuple[bytes, bytes]:
    """A little-endian IFD; values over 4 bytes go to the data area that starts at `data_at`."""
    head, data = struct.pack("<H", len(entries)), b""
    for tag, kind, count, value in entries:
        if len(value) <= 4:
            head += struct.pack("<HHI", tag, kind, count) + value.ljust(4, b"\x00")
        else:
            head += struct.pack("<HHII", tag, kind, count, data_at + len(data))
            data += value + (b"\x00" if len(value) % 2 else b"")
    return head + struct.pack("<I", next_ifd), data


def raw_exif_with_thumbnail(thumb: bytes | None = None, *, offset_shift: int = 0) -> bytes:
    """A hand-made EXIF block: IFD0 (Make) and IFD1 pointing at a JPEG thumbnail."""
    thumb = thumbnail_jpeg() if thumb is None else thumb
    make = b"Thumb Maker\x00"
    ifd0_at, ifd1_at = 8, 8 + 2 + 12 + 4 + len(make)
    ifd0, data0 = _ifd([(0x010F, 2, len(make), make)], ifd1_at, ifd0_at + 2 + 12 + 4)
    thumb_at = ifd1_at + 2 + 3 * 12 + 4
    ifd1, _ = _ifd(
        [
            (0x0103, 3, 1, struct.pack("<H", 6)),
            (0x0201, 4, 1, struct.pack("<I", thumb_at + offset_shift)),
            (0x0202, 4, 1, struct.pack("<I", len(thumb))),
        ],
        0,
        0,
    )
    return b"Exif\x00\x00" + b"II*\x00" + struct.pack("<I", ifd0_at) + ifd0 + data0 + ifd1 + thumb


def iptc_block(datasets: list[tuple[int, int, bytes]]) -> bytes:
    """IPTC-IIM datasets in a Photoshop 8BIM 0x0404 resource, as JPEG APP13 carries it."""
    iim = b"".join(b"\x1c" + bytes([r, d]) + struct.pack(">H", len(v)) + v for r, d, v in datasets)
    resource = b"8BIM\x04\x04\x00\x00" + struct.pack(">I", len(iim)) + iim + (b"\x00" if len(iim) % 2 else b"")
    return b"Photoshop 3.0\x00" + resource


def with_segment(jpeg_bytes: bytes, marker: int, payload: bytes) -> bytes:
    """Insert one APPn segment right after the JPEG's SOI marker."""
    assert jpeg_bytes[:2] == b"\xff\xd8"
    return jpeg_bytes[:2] + bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload + jpeg_bytes[2:]


def iptc_jpeg() -> bytes:
    datasets = [
        (1, 90, b"\x1b%G"),
        (2, 5, "Predmet št. 12".encode()),
        (2, 25, b"finger"),
        (2, 25, b"synthetic"),
        (2, 80, b"Examiner A"),
        (2, 90, b"Ljubljana"),
        (2, 200, b"custom"),
    ]
    return with_segment(jpeg(icc=False), 0xED, iptc_block(datasets))


def png(
    *, exif: Image.Exif | None = None, texts: dict[str, str] | None = None, xmp_packet: bytes | None = None
) -> bytes:
    info = PngImagePlugin.PngInfo()
    for key, value in (texts or {}).items():
        if value.isascii():
            info.add_text(key, value)
        else:
            info.add_itxt(key, value)
    if xmp_packet is not None:
        info.add_itxt("XML:com.adobe.xmp", xmp_packet.decode())
    buf = io.BytesIO()
    extra: dict[str, Any] = {"pnginfo": info}
    if exif is not None:
        extra["exif"] = exif
    small_image().save(buf, "PNG", **extra)
    return buf.getvalue()


def save(fmt: str, **extra: Any) -> bytes:
    buf = io.BytesIO()
    small_image().save(buf, fmt, **extra)
    return buf.getvalue()


def finger_png_with_gps() -> bytes:
    """A synthetic finger photo (golden case whorl_default) as PNG with camera EXIF and GPS."""
    rgb = CASES_BY_NAME["whorl_default"].photo()[:, :, ::-1]
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(rgb)).save(buf, "PNG", exif=camera_exif(orientation=1))
    return buf.getvalue()
