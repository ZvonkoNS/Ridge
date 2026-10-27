"""Folder triage: which photos in a folder show a measurable ridge pattern (PRD FR-57; indicative, never a score).

A seized phone or a case folder holds many photographs, and few of them show a finger. The triage
runs the capture check (FR-54) on every photo of a folder, each read once and read-only, and sorts
the results so that the photos where a finger was located and a clear ridge wave was measured come
first. Nothing is written next to the photos: the index goes where the examiner says, and the
originals are never changed. The order is a reading order for the examiner, who still looks at
every photo. A photo at the bottom is not "no print" and a photo at the top is not "a usable
print"; nothing is discarded, nothing is submitted, and nothing is said about identification.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from ridge import __version__
from ridge.capture import (
    MAX_GLARE_SHARE,
    MIN_CLARITY,
    MIN_FINGER_SHARE,
    MIN_PIXELS_PER_RIDGE,
    CaptureCheck,
    check_bytes,
)
from ridge.errors import ExtractionError, InputError, InputRejectedError, OutputError, OutputExistsError, ParameterError
from ridge.image_io import IMAGE_EXTS, ReadLimits, publish, read_bounded

SCHEMA: Final = "ridge.triage/1"
DEFAULT_MAX_FILES: Final = 1000  # one folder per run; the check takes a few seconds per photo, whatever its size
HARD_MAX_FILES: Final = 10_000
NOTICE: Final = (
    "This is a reading order for the examiner, who still looks at every photo. It says which photos show a "
    "measurable ridge pattern, not which show a usable print, and it says nothing about identification."
)

Group = Literal["finger-ridges", "ridges-no-finger", "finger-unclear", "nothing", "refused"]
GROUPS: Final[tuple[Group, ...]] = ("finger-ridges", "ridges-no-finger", "finger-unclear", "nothing", "refused")
GROUP_TEXT: Final[dict[Group, str]] = {
    "finger-ridges": "a finger was located by skin colour and its patches show a clear ridge wave",
    "ridges-no-finger": (
        "no finger was located by skin colour, but the frame shows a clear ridge-like wave "
        "(a finger in grey or odd light, or a texture)"
    ),
    "finger-unclear": "a finger was located, but its ridge pattern is unclear or its spacing could not be measured",
    "nothing": "no finger was located and no clear ridge-like wave was measured",
    "refused": "not read: not a supported image, over a limit, a link, not a regular file, or unreadable",
}
COLUMNS: Final = (
    "order",
    "group",
    "file",
    "bytes",
    "sha256",
    "width_px",
    "height_px",
    "finger_located",
    "finger_share",
    "ridge_spacing_px",
    "clarity",
    "glare_share",
    "capture_verdict",
    "findings",
    "reason",
)
_ORDER: Final = {group: index for index, group in enumerate(GROUPS)}


@dataclass(frozen=True, slots=True)
class TriageRow:
    """One file of the folder: its capture check and group, or why it was not read."""

    file: str  # path relative to the folder, with "/" separators
    size: int  # bytes on disk
    group: Group
    check: CaptureCheck | None  # None when the file was refused
    reason: str = ""  # why the file was refused (empty when it was checked)

    @property
    def clarity(self) -> float | None:
        """The capture check's clarity (median spectral peak share, 0..1), or None when not measured."""
        return None if self.check is None else self.check.clarity

    def to_json(self) -> dict[str, Any]:
        """Report form of the row; the check's own notice is left to the triage record."""
        check = None if self.check is None else {k: v for k, v in self.check.to_json().items() if k != "notice"}
        return {"file": self.file, "bytes": self.size, "group": self.group, "check": check, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class Triage:
    """A checked folder: its rows in reading order and what was not read at all."""

    folder: Path
    recursive: bool
    rows: tuple[TriageRow, ...]  # in reading order
    other_files: int  # files without an image extension: not opened

    def count(self, group: Group) -> int:
        """Return how many rows fall in `group`."""
        return sum(row.group == group for row in self.rows)

    def to_json(self, index: tuple[Path, str] | None = None) -> dict[str, Any]:
        """Return the ``ridge.triage/1`` record; `index` is the written index's (path, SHA-256), when any."""
        record = {
            "schema": SCHEMA,
            "ridge_version": __version__,
            "folder": str(self.folder),
            "recursive": self.recursive,
            "photos": len(self.rows),
            "other_files": self.other_files,
            "counts": {group: self.count(group) for group in GROUPS},
            "groups": dict(GROUP_TEXT),
            "thresholds": {
                "min_finger_share": MIN_FINGER_SHARE,
                "min_pixels_per_ridge": MIN_PIXELS_PER_RIDGE,
                "min_clarity": MIN_CLARITY,
                "max_glare_share": MAX_GLARE_SHARE,
            },
            "rows": [{"order": order, **row.to_json()} for order, row in enumerate(self.rows, start=1)],
            "notice": NOTICE,
        }
        if index is not None:
            record["index"] = {"path": str(index[0]), "sha256": index[1]}
        return record


def group_of(check: CaptureCheck) -> Group:
    """Classify a capture check by what it measured: a located finger and a clear ridge wave."""
    clear = check.clarity is not None and check.clarity >= MIN_CLARITY  # the check's "clarity" finding
    if check.finger_located:
        return "finger-ridges" if clear else "finger-unclear"
    return "ridges-no-finger" if clear else "nothing"


def _reading_order(row: TriageRow) -> tuple[int, float, str]:
    """Group first, then the clearest ridge wave, then the file name; stable for identical folders."""
    clarity = -1.0 if row.clarity is None else row.clarity  # unmeasured sorts after every measured value
    return (_ORDER[row.group], -clarity, row.file)


def _entries(folder: Path, recursive: bool) -> Iterator[Path]:
    """Yield the files of `folder`; subfolders only when `recursive`, and never through a link (CWE-59)."""
    for entry in folder.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            if recursive:
                yield from _entries(entry, recursive)
        else:
            yield entry


def list_photos(folder: Path, *, recursive: bool = False) -> tuple[list[Path], int]:
    """Return (files with an image extension in reading order, count of other files). Nothing is opened."""
    if not folder.is_dir():
        raise InputError(f"{folder} is not a folder")
    photos, other = [], 0
    for entry in _entries(folder, recursive):
        if entry.suffix.lower() in IMAGE_EXTS:
            photos.append(entry)
        else:
            other += 1
    photos.sort(key=lambda path: path.relative_to(folder).as_posix())  # the same order on every platform
    return photos, other


def _check_one(folder: Path, path: Path, limits: ReadLimits) -> TriageRow:
    """Run the capture check on one file; a refused or unreadable file becomes a row, never a stop."""
    name = path.relative_to(folder).as_posix()
    if path.is_symlink():  # never follow a link found in an evidence folder (CWE-59)
        return TriageRow(name, 0, "refused", None, "a link, not a regular file")
    size = 0
    try:
        size = path.stat().st_size
        data = read_bounded(path, limits.max_bytes)
        check = check_bytes(data, limits)
    except (InputError, ExtractionError) as exc:  # not an image, over a limit, corrupt, or unmeasurable
        return TriageRow(name, size, "refused", None, str(exc))
    except OSError as exc:
        return TriageRow(name, size, "refused", None, f"cannot be read ({exc.strerror or type(exc).__name__})")
    return TriageRow(name, size, group_of(check), check)


def triage_folder(
    folder: Path, *, recursive: bool = False, max_files: int = DEFAULT_MAX_FILES, limits: ReadLimits | None = None
) -> Triage:
    """Check every photo of `folder` (read once, read-only) and return the rows in reading order."""
    if not 1 <= max_files <= HARD_MAX_FILES:
        raise ParameterError(f"--max-files must be between 1 and {HARD_MAX_FILES}")
    photos, other = list_photos(folder, recursive=recursive)
    if not photos:
        raise InputError(f"no photo ({', '.join(sorted(IMAGE_EXTS))}) in {folder}")
    if len(photos) > max_files:
        raise InputRejectedError(
            f"{folder} holds {len(photos)} photos; the limit is {max_files} (--max-files, at most {HARD_MAX_FILES}): "
            "check a smaller folder"
        )
    limits = limits or ReadLimits()
    rows = sorted((_check_one(folder, path, limits) for path in photos), key=_reading_order)
    return Triage(folder, recursive, tuple(rows), other)


def run_triage(
    folder: Path, *, recursive: bool = False, max_files: int = DEFAULT_MAX_FILES, dest: Path | None = None
) -> tuple[Triage, tuple[Path, str] | None]:
    """Check the folder and, with `dest`, write the index; the destination is checked before the long read."""
    if dest is not None:
        check_destination(folder, dest)
    triage = triage_folder(folder, recursive=recursive, max_files=max_files)
    written = None if dest is None else (dest, write_index(triage, dest))
    return triage, written


def _number(value: float | None, digits: int) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def _csv_row(order: int, row: TriageRow) -> list[str]:
    head = [str(order), row.group, row.file, str(row.size)]
    if row.check is None:
        return [*head, *([""] * 10), row.reason]
    check = row.check
    return [
        *head,
        check.sha256,
        str(check.width),
        str(check.height),
        "yes" if check.finger_located else "no",
        f"{check.finger_share:.4f}",
        _number(check.ridge_spacing_px, 2),
        _number(check.clarity, 4),
        _number(check.glare_share, 4),
        check.verdict,
        " ".join(f"{finding.level}:{finding.id}" for finding in check.findings),
        "",
    ]


def index_bytes(triage: Triage) -> bytes:
    """Return the CSV index (UTF-8, LF): one row per file in reading order, the same bytes for the same folder."""
    buffer = io.StringIO()
    rows = csv.writer(buffer, lineterminator="\n")
    rows.writerow(COLUMNS)
    rows.writerows(_csv_row(order, row) for order, row in enumerate(triage.rows, start=1))
    # A file name the file system could not decode is shown escaped, so the index stays valid UTF-8.
    return buffer.getvalue().encode("utf-8", errors="backslashreplace")


def check_destination(folder: Path, dest: Path) -> None:
    """Refuse an index destination that exists, is not a .csv, has no folder, or lies inside the scanned folder."""
    if dest.suffix.lower() != ".csv":
        raise OutputError(f"the index must be a .csv file, not {dest.name}")
    if not dest.parent.is_dir():
        raise OutputError(f"the folder for {dest.name} does not exist: {dest.parent}")
    if dest.exists() or dest.is_symlink():
        raise OutputExistsError(f"{dest} already exists: choose a new name (an index is never replaced)")
    inside = {folder.absolute(), folder.resolve()}
    for candidate in (dest.absolute(), dest.resolve()):
        if any(parent in inside for parent in candidate.parents):
            raise OutputError(
                f"{dest.name} would be written inside the scanned folder: nothing is written next to the photos"
            )


def write_index(triage: Triage, dest: Path) -> str:
    """Write the CSV index to the new file `dest` (atomic, never replacing a file) and return its SHA-256."""
    check_destination(triage.folder, dest)
    data = index_bytes(triage)
    publish(dest, data)
    return hashlib.sha256(data).hexdigest()


def row_text(order: int, row: TriageRow) -> str:
    """One terminal line for a row: its place, group, clarity or reason, and file name."""
    detail = row.reason if row.check is None else f"clarity {_number(row.clarity, 3) or '-'}"
    return f"{order:>5}  {row.group:<17} {detail:<14}  {row.file}"


def triage_text(triage: Triage, *, index: tuple[Path, str] | None = None) -> list[str]:
    """Summary lines for the terminal: what was checked, the groups with their counts, the index, the notice."""
    heading = f"triage of {triage.folder}: {len(triage.rows)} photo(s) checked"
    if triage.recursive:
        heading += ", subfolders included"
    if triage.other_files:
        heading += f", {triage.other_files} other file(s) not read"
    lines = [heading]
    lines.extend(f"  {triage.count(g):>5}  {g:<17} {GROUP_TEXT[g]}" for g in GROUPS if triage.count(g))
    if index is not None:
        lines.append(f"index written to {index[0]} (SHA-256 {index[1]})")
    lines.append(NOTICE)
    return lines
