"""Export every stored item of one role at once (FR-32).

For example all comparison exports for the AFIS operator. Each file leaves the store through
`OpenCase.export`, so each is logged as its own ``artefact.export``. The folder must be new, and an
index (``EXPORTS.csv``) names every file's SHA-256, role, job and source label, so the receiver can
match them to the signed reports.

If an export fails part-way, the files already written stay (each is in the custody log), the index
lists exactly those, and the error says how many of how many were exported.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from ridge.case.case_model import StoredItem
from ridge.case.store import OpenCase
from ridge.errors import OutputError, OutputExistsError, ParameterError, RidgeError
from ridge.image_io import publish

ROLES = ("export", "print", "minutiae", "evidence", "reference")
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


def export_role(case: OpenCase, role: str, dest: Path) -> list[tuple[StoredItem, str]]:
    """Export every item of `role` into the new folder `dest`; return each item with its file name."""
    if role not in ROLES:
        raise ParameterError(f"the role must be one of {', '.join(ROLES)}")
    items = [i for i in case.items() if i.role == role]
    if not items:
        raise ParameterError(f"no {role} items are stored in this case")
    try:
        dest.mkdir(mode=0o700)  # private: file names carry labels and hash prefixes
    except FileExistsError:
        raise OutputExistsError(f"{dest.name} already exists: choose a new folder") from None
    written: list[tuple[StoredItem, str]] = []
    try:
        for item, name in zip(items, file_names(items), strict=True):
            case.export(item.sha256, dest / name)  # logged as artefact.export, never over a file
            written.append((item, name))
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


def _write_index(dest: Path, written: list[tuple[StoredItem, str]]) -> None:
    buffer = io.StringIO()
    rows = csv.writer(buffer, lineterminator="\n")
    rows.writerow(["file", "sha256", "role", "job_id", "label"])
    rows.writerows([_cell(name), i.sha256, i.role, i.job_id or "", _cell(i.label)] for i, name in written)
    publish(dest / INDEX, buffer.getvalue().encode("utf-8"))
