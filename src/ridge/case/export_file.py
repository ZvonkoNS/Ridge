"""Export one stored item to a file, converted to TIFF or BMP when the name asks for it (PRD FR-32).

`OpenCase.export` writes the stored bytes. This module adds the exchange formats of
`ridge.export.formats` for Ridge's own image outputs: the destination's suffix chooses the format,
the file leaves the store through the same publish-then-log path (FR-22, FR-25), and the custody
entry (``artefact.export``) names the stored item's SHA-256, the format and the SHA-256 of the
bytes written, so a converted file can be matched to its stored original.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ridge.case.case_model import publish_logged
from ridge.case.crypto import sha256_hex
from ridge.case.store import OpenCase
from ridge.export.formats import EXTENSIONS, FileFormat, convert_png, format_for

CONVERTIBLE_ROLES: Final = ("export", "export-gray", "print", "debug")  # Ridge's own PNG outputs


@dataclass(frozen=True, slots=True)
class ExportedFile:
    """What was written: the destination, the SHA-256 of its bytes and the format (None: bytes as stored)."""

    path: Path
    sha256: str
    format: FileFormat | None


def export_item(case: OpenCase, sha: str, dest: Path, *, overwrite: bool = False) -> ExportedFile:
    """Write one stored item to `dest`, converted when the suffix asks for TIFF or BMP (logged either way)."""
    item = case.item(sha)
    fmt = format_for(dest)
    if fmt is None or fmt == "png" or item.role not in CONVERTIBLE_ROLES:
        case.export(item.sha256, dest, overwrite=overwrite)
        return ExportedFile(dest, item.sha256, None)
    data = convert_png(case.read(item.sha256, log=False), fmt)
    written = sha256_hex(data)
    publish_logged(
        [(dest, data)],
        lambda: case.entries.append(
            case.custody.append(
                "artefact.export",
                sha256=item.sha256,
                role=item.role,
                destination=str(dest.resolve()),
                format=fmt,
                written_sha256=written,
            )
        ),
        overwrite=overwrite,
    )
    return ExportedFile(dest, written, fmt)


def converted_name(name: str, fmt: FileFormat | None, role: str) -> str:
    """Return the file name for an export of `role` in `fmt`: the PNG suffix replaced for convertible roles."""
    if fmt is None or fmt == "png" or role not in CONVERTIBLE_ROLES:
        return name
    stem, dot, _ = name.rpartition(".")
    return (stem if dot else name) + EXTENSIONS[fmt]
