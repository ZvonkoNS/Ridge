"""Display-safe, bounded text for metadata values read from untrusted files.

Metadata is attacker-controlled: any editor can write any bytes into it. Every value shown or
recorded passes through `text`, which removes what could make the shown text differ from the
stored one (control characters, bidirectional overrides, zero-width characters, CWE-150), and
every entry is counted against a `Budget`, so a file cannot make a report or an RPC response grow
without bound (CWE-400, CWE-770). Binary values are summarised by size and SHA-256, never copied.
"""

from __future__ import annotations

import hashlib
import re
import struct
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

MAX_ENTRIES = 2000  # far above a phone photo (about 150); bounds the report and the RPC response
MAX_VALUE_BYTES = 2000  # UTF-8 bytes of one shown value
MAX_TOTAL_BYTES = 200_000  # UTF-8 bytes of all names and values together
MAX_ITEMS = 32  # values of one array shown before the rest is counted
SHORT_BINARY = 16  # binary values up to this size are shown in hex

# What Pillow's parsers and the XML reader raise on malformed metadata. A group that fails with
# one of these is reported as unreadable; anything else is a bug and propagates.
READ_FAILURES: tuple[type[Exception], ...] = (
    OSError,
    SyntaxError,  # includes xml.etree.ElementTree.ParseError
    ValueError,  # includes UnicodeError and defusedxml's DefusedXmlException
    EOFError,
    struct.error,
    IndexError,
    KeyError,
    TypeError,
    ZeroDivisionError,
    OverflowError,
    zlib.error,
)

# Shown as <U+XXXX>: C0/C1 controls, DEL, bidirectional marks, overrides and isolates (CVE-2021-42574),
# zero-width characters, word joiners, the byte order mark and interlinear annotation characters.
_HIDDEN_RANGES = (
    (0x00, 0x1F),  # C0 controls
    (0x7F, 0x9F),  # DEL and C1 controls
    (0x061C, 0x061C),  # Arabic letter mark
    (0x200B, 0x200F),  # zero-width space, joiners, left-to-right and right-to-left marks
    (0x202A, 0x202E),  # bidirectional embeddings and overrides
    (0x2060, 0x2069),  # word joiner, invisible operators, bidirectional isolates
    (0xFEFF, 0xFEFF),  # byte order mark
    (0xFFF9, 0xFFFB),  # interlinear annotation
)
_HIDDEN = re.compile("[" + "".join(f"{re.escape(chr(a))}-{re.escape(chr(b))}" for a, b in _HIDDEN_RANGES) + "]")
_CONTROLS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_SPACES = re.compile("[\t\n\r]+")


def text(value: str) -> str:
    """Return `value` safe to show: trailing NULs dropped, line breaks and tabs as spaces, hidden characters visible."""
    value = _SPACES.sub(" ", value.rstrip("\x00"))
    return _HIDDEN.sub(lambda m: f"<U+{ord(m.group()):04X}>", value)


def from_latin1(value: str) -> str:
    """Undo Pillow's Latin-1 reading of an EXIF ASCII string that is really UTF-8 (phones write UTF-8)."""
    try:
        raw = value.encode("latin-1")
    except UnicodeEncodeError:
        return value
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return value


def sha256(data: bytes) -> str:
    """Lowercase hex SHA-256 with the algorithm label, as Ridge writes hashes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def binary(data: bytes, what: str = "binary data") -> str:
    """Summarise binary data: short values in hex, longer ones by size and hash."""
    if len(data) <= SHORT_BINARY:
        return f"{what}, {len(data)} bytes: " + (data.hex(" ") if data else "empty")
    return f"{what}, {len(data):,} bytes, {sha256(data)}"


def as_text(data: bytes) -> str | None:
    """Return `data` as text when it is UTF-8 without control characters (NULs at the end allowed), else None."""
    try:
        decoded = data.rstrip(b"\x00").decode("utf-8")
    except UnicodeDecodeError:
        return None
    return decoded if decoded and not _CONTROLS.search(decoded) else None


def number(value: Fraction, digits: int = 10) -> str:
    """Exact decimal form of a rational when it is short, else up to `digits` significant digits and the ratio."""
    if value.denominator == 1:
        return str(value.numerator)
    shown = f"{value:.{digits}g}"
    if Fraction(shown) == value:
        return shown
    return f"{shown} ({value.numerator}/{value.denominator})"


def rational(numerator: int, denominator: int) -> str:
    """Show an EXIF rational faithfully, including the undefined n/0."""
    if denominator == 0:
        return f"undefined ({numerator}/0)"
    return number(Fraction(numerator, denominator))


def describe(value: Any) -> str:
    """Show any value Pillow returns for a metadata tag."""
    if isinstance(value, str):
        return from_latin1(value)
    if isinstance(value, bytes):
        if len(value) == 1:  # a single EXIF BYTE is a number (codes such as GPSAltitudeRef)
            return str(value[0])
        shown = as_text(value)
        return binary(value) if shown is None else shown
    if hasattr(value, "numerator") and hasattr(value, "denominator") and not isinstance(value, int):
        return rational(int(value.numerator), int(value.denominator))
    if isinstance(value, tuple | list):
        return items(describe(v) for v in value)
    return str(value)


def items(values: Iterable[str]) -> str:
    """Join array values, showing at most MAX_ITEMS and counting the rest."""
    shown: list[str] = []
    total = 0
    for value in values:
        total += 1
        if total <= MAX_ITEMS:
            shown.append(value)
    rest = f", ... ({total} values in all)" if total > MAX_ITEMS else ""
    return ", ".join(shown) + rest


@dataclass
class Budget:
    """Counts entries and bytes; past the limits, entries are dropped and counted."""

    entries: int = 0
    used: int = 0
    dropped: int = 0
    shortened: int = 0
    notes: list[str] = field(default_factory=list)

    def entry(self, name: str, value: str, ident: str | None = None) -> dict[str, str] | None:
        """Return a display-safe entry, or None when the budget is spent."""
        name, value = text(name)[:200], self._fit(text(value))
        size = len(name.encode("utf-8")) + len(value.encode("utf-8"))
        if self.entries >= MAX_ENTRIES or self.used + size > MAX_TOTAL_BYTES:
            self.dropped += 1
            return None
        self.entries += 1
        self.used += size
        return {"name": name, "value": value} if ident is None else {"name": name, "id": ident, "value": value}

    def _fit(self, value: str) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= MAX_VALUE_BYTES:
            return value
        self.shortened += 1
        cut = encoded[: MAX_VALUE_BYTES - 64].decode("utf-8", "ignore")
        return f"{cut} ... (shortened: {len(value):,} characters in all)"
