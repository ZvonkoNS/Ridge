"""Export every stored item of one role at once (FR-32).

For example all comparison exports for the AFIS operator. Each file leaves the store through
`OpenCase.export`, so each is logged as its own ``artefact.export``. The folder must be new, and an
index (``EXPORTS.csv``) names every file's SHA-256, role, job and source label, so the receiver can
match them to the signed reports.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from ridge.case.store import OpenCase, StoredItem
from ridge.errors import OutputExistsError, ParameterError
from ridge.image_io import publish

ROLES = ("export", "print", "minutiae", "evidence", "reference")
INDEX = "EXPORTS.csv"
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def file_name(item: StoredItem) -> str:
    """Return a safe, unique file name: the stored label's name with the first 12 hex of its SHA-256."""
    label = Path(item.label).name or item.role
    stem, dot, suffix = label.rpartition(".")
    stem, suffix = (stem, suffix) if dot else (label, "")
    safe = _UNSAFE.sub("_", stem).strip("._")[:80] or item.role
    return f"{safe}_{item.sha256[:12]}" + (f".{_UNSAFE.sub('_', suffix)[:10]}" if suffix else "")


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
        dest.mkdir()
    except FileExistsError:
        raise OutputExistsError(f"{dest.name} already exists: choose a new folder") from None
    written = []
    for item in items:
        name = file_name(item)
        case.export(item.sha256, dest / name)  # logged as artefact.export, never over a file
        written.append((item, name))
    buffer = io.StringIO()
    rows = csv.writer(buffer, lineterminator="\n")
    rows.writerow(["file", "sha256", "role", "job_id", "label"])
    rows.writerows([_cell(name), i.sha256, i.role, i.job_id or "", _cell(i.label)] for i, name in written)
    publish(dest / INDEX, buffer.getvalue().encode("utf-8"))
    return written
