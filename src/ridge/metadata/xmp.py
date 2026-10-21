"""XMP: every property of every rdf:Description, flattened to ``prefix:Name`` and its value.

The packet is parsed with defusedxml, which refuses DTDs, entity declarations and external
references (CWE-611, CWE-776), so a hostile packet cannot expand or fetch anything. Lists are
joined with "; ", structures are named ``parent/child`` and list items ``name[1]/child``, so an
edit history (xmpMM:History) is shown step by step. Packets above MAX_XMP_BYTES are not parsed;
a packet that fails to parse is shown as raw text, shortened like any long value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import defusedxml.ElementTree as SafeElementTree  # type: ignore[import-untyped]

from ridge.metadata.values import READ_FAILURES, Budget, binary

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML_NS = "http://www.w3.org/XML/1998/namespace"
EXIF_NS = "http://ns.adobe.com/exif/1.0/"
XMP_NS = "http://ns.adobe.com/xap/1.0/"
MAX_XMP_BYTES = 1024 * 1024  # a JPEG XMP segment is at most 64 KiB; edit histories rarely exceed this
MAX_DEPTH = 16
KNOWN_PREFIXES = {
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://ns.adobe.com/xap/1.0/": "xmp",
    "http://ns.adobe.com/xap/1.0/mm/": "xmpMM",
    "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#": "stEvt",
    "http://ns.adobe.com/xap/1.0/sType/ResourceRef#": "stRef",
    "http://ns.adobe.com/xap/1.0/rights/": "xmpRights",
    "http://ns.adobe.com/exif/1.0/": "exif",
    "http://cipa.jp/exif/1.0/": "exifEX",
    "http://ns.adobe.com/tiff/1.0/": "tiff",
    "http://ns.adobe.com/photoshop/1.0/": "photoshop",
    "http://ns.adobe.com/camera-raw-settings/1.0/": "crs",
    "http://ns.adobe.com/exif/1.0/aux/": "aux",
    "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/": "Iptc4xmpCore",
    "http://iptc.org/std/Iptc4xmpExt/2008-02-29/": "Iptc4xmpExt",
    "http://ns.google.com/photos/1.0/camera/": "GCamera",
    "http://ns.google.com/photos/1.0/image/": "GImage",
    "http://ns.apple.com/HDRGainMap/1.0/": "HDRGainMap",
    "http://ns.apple.com/ImageIO/1.0/": "iio",
}
_DECLARED = re.compile(r"""xmlns:([A-Za-z_][\w.-]*)\s*=\s*["']([^"']*)["']""")
_CONTAINERS = {f"{{{RDF}}}{kind}" for kind in ("Seq", "Bag", "Alt")}
Element = Any  # an ElementTree element made by defusedxml (xml.etree is not imported directly: bandit B405)


@dataclass
class XmpRead:
    """The XMP entries, the GPS strings (exif:GPSLatitude, exif:GPSLongitude) and xmp:CreatorTool if recorded."""

    entries: list[dict[str, str]] = field(default_factory=list)
    gps_latitude: str | None = None
    gps_longitude: str | None = None
    creator_tool: str | None = None


class _Flattener:
    def __init__(self, prefixes: dict[str, str]) -> None:
        self.prefixes = prefixes
        self.found: list[tuple[str, str]] = []
        self.top: dict[str, str] = {}  # "{uri}local" of top-level simple values

    def name(self, tag: str) -> str:
        if not tag.startswith("{"):
            return tag
        uri, local = tag[1:].split("}", 1)
        prefix = self.prefixes.get(uri) or KNOWN_PREFIXES.get(uri)
        return f"{prefix}:{local}" if prefix else tag

    def add(self, path: str, tag: str, value: str) -> None:
        self.found.append((path + self.name(tag), value))
        if not path:
            self.top.setdefault(tag, value)

    def properties(self, node: Element, path: str, depth: int) -> None:
        for key, value in node.attrib.items():
            if not key.startswith((f"{{{RDF}}}", f"{{{XML_NS}}}")):
                self.add(path, key, value)
        for child in node:
            self.value(child, path, depth + 1)

    def value(self, element: Element, path: str, depth: int) -> None:
        name = path + self.name(element.tag)
        if depth > MAX_DEPTH:
            self.found.append((name, "(nested too deeply; not read)"))
            return
        if (resource := element.get(f"{{{RDF}}}resource")) is not None:
            self.add(path, element.tag, resource)
        kids = list(element)
        if kids and kids[0].tag in _CONTAINERS:
            self.container(kids[0], name, depth)
        elif kids or element.get(f"{{{RDF}}}parseType") == "Resource":
            inner = kids[0] if len(kids) == 1 and kids[0].tag == f"{{{RDF}}}Description" else element
            self.properties(inner, name + "/", depth)
        elif resource is None:
            if any(not k.startswith((f"{{{RDF}}}", f"{{{XML_NS}}}")) for k in element.attrib):
                self.properties(element, name + "/", depth)
            else:
                self.add(path, element.tag, (element.text or "").strip())

    def container(self, box: Element, name: str, depth: int) -> None:
        simple: list[str] = []
        for i, item in enumerate(box, start=1):
            if len(item) or any(not k.startswith((f"{{{RDF}}}", f"{{{XML_NS}}}")) for k in item.attrib):
                inner = item[0] if len(item) == 1 and item[0].tag == f"{{{RDF}}}Description" else item
                self.properties(inner, f"{name}[{i}]/", depth + 1)
                continue
            text = (item.text or "").strip()
            lang = item.get(f"{{{XML_NS}}}lang")
            simple.append(f"{lang}: {text}" if lang and lang != "x-default" else text)
        if simple:
            self.found.append((name, "; ".join(simple)))


def read_xmp(packet: bytes, budget: Budget, warnings: list[str]) -> XmpRead:
    """Entries for an XMP packet; refuses DTDs and entities, never fails the caller."""
    found = XmpRead()
    if len(packet) > MAX_XMP_BYTES:
        warnings.append(f"The XMP packet is larger than {MAX_XMP_BYTES // 1024} KiB and was not parsed.")
        entry = budget.entry("XMP packet", binary(packet, "XMP packet, not parsed"))
        found.entries = [entry] if entry else []
        return found
    shown = packet.decode("utf-8", "replace")
    try:
        root = SafeElementTree.fromstring(packet, forbid_dtd=True)
    except READ_FAILURES as exc:
        warnings.append(
            f"The XMP packet could not be read safely ({type(exc).__name__}): it is not well-formed XML or it "
            "declares a DTD or entities, which Ridge refuses. It is listed as raw text."
        )
        entry = budget.entry("XMP packet (raw text)", shown)
        found.entries = [entry] if entry else []
        return found
    prefixes: dict[str, str] = {}
    for prefix, uri in _DECLARED.findall(shown):
        prefixes.setdefault(uri, prefix)
    flat = _Flattener(prefixes)
    for rdf in root.iter(f"{{{RDF}}}RDF"):
        for description in rdf:
            if description.tag == f"{{{RDF}}}Description":
                flat.properties(description, "", 0)
    found.entries = [e for e in (budget.entry(n, v) for n, v in flat.found) if e is not None]
    found.gps_latitude = flat.top.get(f"{{{EXIF_NS}}}GPSLatitude")
    found.gps_longitude = flat.top.get(f"{{{EXIF_NS}}}GPSLongitude")
    found.creator_tool = flat.top.get(f"{{{XMP_NS}}}CreatorTool")
    return found
