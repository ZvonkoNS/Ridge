"""Export every stored item of one role at once (FR-32).

For example all comparison exports for the AFIS operator. Each file leaves the store through
`export_file.export_item` (the stored bytes, or a TIFF/BMP conversion when a format is asked for),
so each is logged as its own ``artefact.export``. The folder must be new, and an index
(``EXPORTS.csv``) names every file's stored SHA-256, role, job, source label, format and the
SHA-256 of the bytes written, so the receiver can match them to the signed reports.

If an export fails part-way, the files already written stay (each is in the custody log), the index
lists exactly those, and the error says how many of how many were exported.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from ridge.case.case_model import StoredItem
from ridge.case.export_file import ExportedFile, converted_name, export_item
from ridge.case.store import OpenCase
from ridge.errors import OutputError, OutputExistsError, ParameterError, RidgeError
from ridge.export.formats import FileFormat, check_format
from ridge.image_io import publish

ROLES = ("export", "export-gray", "print", "minutiae", "evidence", "reference")
INDEX = "EXPORTS.csv"
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def file_name(item: StoredItem, digits: int = 12) -> str:
    """Return a safe file name: the stored label's name with the first `digits` hex of its SHA-256."""
    label = Path(item.label).name or item.role
    stem, dot, suffix = label.rpartition(".")
    stem, suffix = (stem, suffix) if dot else (label, "")
    safe = _UNSAFE.sub("_", stem).strip("._")[:80] or item.role
    return f"{safe}_{item.sha256[:digits]}" + (f".{_UNSAFE.sub('_', suffix)[:10]}" if suffix else "")


def file_names(items: list[StoredItem]) -> list[str]:
    """Return a distinct name for each item, compared without case (as Windows and macOS do).

    A name already taken uses the full SHA-256, then a counter, so two items whose hashes share a
    prefix, or whose labels differ only in case, are both exported.
    """
    used: set[str] = set()
    names = []
    for item in items:
        name = file_name(item)
        if name.lower() in used:
            name = file_name(item, 64)
        base, n = name, 2
        while name.lower() in used:
            stem, dot, suffix = base.rpartition(".")
            name = f"{stem}-{n}.{suffix}" if dot else f"{base}-{n}"
            n += 1
        used.add(name.lower())
        names.append(name)
    return names


def _cell(value: str) -> str:
    """Keep a spreadsheet from reading a label as a formula (CWE-1236)."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value  # labels never hold control characters


@dataclass(frozen=True, slots=True)
class Written:
    """One exported item: the stored item, its file name in the folder and what was written."""

    item: StoredItem
    name: str
    file: ExportedFile


def export_role(case: OpenCase, role: str, dest: Path, *, fmt: FileFormat | None = None) -> list[Written]:
    """Export every item of `role` into the new folder `dest`, converted to `fmt` where that applies."""
    if role not in ROLES:
        raise ParameterError(f"the role must be one of {', '.join(ROLES)}")
    if fmt is not None:
        fmt = check_format(fmt)
    items = [i for i in case.items() if i.role == role]
    if not items:
        raise ParameterError(f"no {role} items are stored in this case")
    try:
        dest.mkdir(mode=0o700)  # private: file names carry labels and hash prefixes
    except FileExistsError:
        raise OutputExistsError(f"{dest.name} already exists: choose a new folder") from None
    written: list[Written] = []
    try:
        for item, name in zip(items, file_names(items), strict=True):
            target = converted_name(name, fmt, item.role)
            written.append(Written(item, target, export_item(case, item.sha256, dest / target)))  # logged
    except (RidgeError, OSError) as exc:
        if not written:
            dest.rmdir()  # nothing left the store: leave nothing behind
            raise
        _write_index(dest, written)
        raise OutputError(
            f"the export stopped after {len(written)} of {len(items)} file(s) ({exc}); {INDEX} lists the "
            "exported files, each is in the custody log"
        ) from exc
    _write_index(dest, written)
    return written


def _write_index(dest: Path, written: list[Written]) -> None:
    buffer = io.StringIO()
    rows = csv.writer(buffer, lineterminator="\n")
    rows.writerow(["file", "sha256", "role", "job_id", "label", "format", "written_sha256"])
    rows.writerows(
        [
            _cell(w.name),
            w.item.sha256,
            w.item.role,
            w.item.job_id or "",
            _cell(w.item.label),
            w.file.format or "as stored",
            w.file.sha256,
        ]
        for w in written
    )
    publish(dest / INDEX, buffer.getvalue().encode("utf-8"))
