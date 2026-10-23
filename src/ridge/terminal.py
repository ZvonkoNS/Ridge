"""Text that is safe to show: no terminal escapes (CWE-150) and no hidden reordering (CVE-2021-42574).

File names, photo metadata, notes and messages that quote them are attacker-controlled. A control
character can drive the examiner's terminal (an escape sequence clears the screen or rewrites a
line), and a bidirectional or zero-width character can reorder or hide what is shown: a file named
``invoice`` + U+202E + ``fdp.exe`` reads as ``invoiceexe.pdf``. Both are written as ``<U+XXXX>``.

``reveal`` is for single values (metadata records, labels). ``safe`` is for what Ridge's
command-line tools print: every line they write passes through it, so no call site can forget.
It shows line breaks too, since a file name with a line break could otherwise print a forged line
of its own (a fake "verification passed"). Output that has several lines by structure, and whose
untrusted parts cannot contain a line break (``json.dumps``, lines built from validated or escaped
values), passes ``lines=True``.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["HIDDEN_RANGES", "reveal", "safe"]

# C0/C1 controls, DEL, bidirectional marks, overrides and isolates, zero-width characters, word
# joiners, the byte order mark and interlinear annotation characters (inclusive code point ranges).
HIDDEN_RANGES: Final = (
    (0x00, 0x1F),  # C0 controls
    (0x7F, 0x9F),  # DEL and C1 controls
    (0x061C, 0x061C),  # Arabic letter mark
    (0x200B, 0x200F),  # zero-width space, joiners, left-to-right and right-to-left marks
    (0x202A, 0x202E),  # bidirectional embeddings and overrides
    (0x2060, 0x2069),  # word joiner, invisible operators, bidirectional isolates
    (0xFEFF, 0xFEFF),  # byte order mark
    (0xFFF9, 0xFFFB),  # interlinear annotation
)
_HIDDEN = re.compile("[" + "".join(f"{re.escape(chr(a))}-{re.escape(chr(b))}" for a, b in HIDDEN_RANGES) + "]")
_TAB = frozenset("\t")  # kept by `safe`; a carriage return could overwrite the line, so it is shown
_TAB_AND_LINES = frozenset("\t\n")  # kept by `safe(..., lines=True)`


def _code(match: re.Match[str]) -> str:
    return f"<U+{ord(match.group()):04X}>"


def reveal(value: str) -> str:
    """`value` with every hidden or control character, line breaks included, written as ``<U+XXXX>``."""
    return _HIDDEN.sub(_code, value)


def safe(value: object, *, lines: bool = False) -> str:
    """`value` as one line for a terminal: like `reveal`, but tabs are kept.

    With `lines=True` line breaks are kept as well: only for text whose untrusted parts cannot
    contain one (JSON from ``json.dumps``, lines built from validated or escaped values).
    """
    keep = _TAB_AND_LINES if lines else _TAB

    def code_unless_kept(match: re.Match[str]) -> str:
        return match.group() if match.group() in keep else _code(match)

    return _HIDDEN.sub(code_unless_kept, str(value))
