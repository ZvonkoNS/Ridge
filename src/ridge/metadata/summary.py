"""The few facts an examiner looks for first, gathered from the EXIF and XMP groups as recorded.

Each summary line names the tags it comes from. Nothing is inferred: a missing tag gives no line,
and times are the camera clock's, with the offset only when the file records one.
"""

from __future__ import annotations

from typing import Any

from ridge.metadata.exif import tag_name
from ridge.metadata.values import Budget, describe

_FACTS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("Camera", (0x010F, 0x0110)),
    ("Lens", (0xA433, 0xA434)),
    ("Software", (0x0131,)),
    ("Artist", (0x013B,)),
    ("Copyright", (0x8298,)),
    ("Camera owner", (0xA430,)),
    ("Camera serial number", (0xA431,)),
    ("Lens serial number", (0xA435,)),
    ("Image unique ID", (0xA420,)),
)
# Date and time, sub-seconds, offset from UTC (EXIF 2.31+)
_TIMES: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("Taken (camera clock)", (0x9003, 0x9291, 0x9011)),
    ("Digitised (camera clock)", (0x9004, 0x9292, 0x9012)),
    ("Changed (camera clock)", (0x0132, 0x9290, 0x9010)),
)


def _shown(tags: dict[int, Any], tag: int) -> str:
    return describe(tags[tag]).strip("\x00 ") if tag in tags else ""


def _time(tags: dict[int, Any], wanted: tuple[int, int, int]) -> str:
    when, sub, offset = (_shown(tags, t) for t in wanted)
    if not when:
        return ""
    return when + (f".{sub}" if sub else "") + (f" {offset}" if offset else "")


def _ratio(value: Any) -> tuple[int, int] | None:
    numerator, denominator = getattr(value, "numerator", None), getattr(value, "denominator", None)
    if isinstance(numerator, int) and isinstance(denominator, int) and denominator:
        return numerator, denominator
    return None


def exposure(tags: dict[int, Any]) -> str:
    """Exposure time, aperture, ISO and focal length as one line (empty when none is recorded)."""
    parts = []
    if (time := _ratio(tags.get(0x829A))) is not None:
        n, d = time
        parts.append(f"1/{d // n} s" if 0 < n < d and d % n == 0 else f"{describe(tags[0x829A])} s")
    if _ratio(tags.get(0x829D)) is not None:
        parts.append(f"f/{describe(tags[0x829D])}")
    if 0x8827 in tags:
        iso = tags[0x8827]
        parts.append(f"ISO {describe(iso[0] if isinstance(iso, tuple) and iso else iso)}")
    if _ratio(tags.get(0x920A)) is not None:
        focal = f"{describe(tags[0x920A])} mm"
        if isinstance(tags.get(0xA405), int) and tags[0xA405]:
            focal += f" ({tags[0xA405]} mm in 35 mm film)"
        parts.append(focal)
    return ", ".join(parts)


def summary(tags: dict[int, Any], xmp_tool: str | None, budget: Budget) -> list[dict[str, str]]:
    """Summary lines, each with the tags it comes from."""
    lines: list[tuple[str, str, str]] = []
    for name, wanted in _FACTS:
        present = [t for t in wanted if _shown(tags, t)]
        if present:
            value = " ".join(_shown(tags, t) for t in present)
            lines.append((name, value, "EXIF " + ", ".join(tag_name(t) for t in present)))
    for name, parts in _TIMES:
        if value := _time(tags, parts):
            lines.append((name, value, "EXIF " + ", ".join(tag_name(t) for t in parts if _shown(tags, t))))
    if shown := exposure(tags):
        used = [tag_name(t) for t in (0x829A, 0x829D, 0x8827, 0x920A, 0xA405) if t in tags]
        lines.append(("Exposure", shown, "EXIF " + ", ".join(used)))
    if xmp_tool:
        lines.append(("Created with (XMP)", xmp_tool, "XMP xmp:CreatorTool"))
    entries = (budget.entry(name, value, source) for name, value, source in lines)
    return [e for e in entries if e is not None]
