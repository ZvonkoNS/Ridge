"""Examiner annotations: minutiae and other features the examiner marks on a job's output image (FR-55).

An annotation set is the examiner's own charting of one output image of one job: numbered marks with
a position, a kind (ending, bifurcation, other) and an optional short label, plus an optional note.
It is a statement by the examiner, kept like a note in the case's custody log (`examiner.annotation`),
and the chain head is signed right after it, so every set is covered by a signature. A newer set for
the same image names the set it replaces; the earlier set stays readable. Ridge draws and lists what
the examiner marked and never interprets it: an annotation is not a match, a count of agreement or
an identification.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any, Final, Literal, cast

from ridge.case.custody import Entry
from ridge.case.identity import Signer
from ridge.case.store import OpenCase
from ridge.errors import ParameterError

ACTION: Final = "examiner.annotation"
KINDS: Final = ("ending", "bifurcation", "other")
IMAGE_ROLES: Final = ("print", "export", "export-gray")  # the output images a set can be about
MAX_MARKS: Final = 500
MAX_LABEL: Final = 40
MAX_NOTE: Final = 2000
_REFUSED: Final = re.compile("[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]")  # control and bidirectional characters
_PNG: Final = b"\x89PNG\r\n\x1a\n"

Kind = Literal["ending", "bifurcation", "other"]


@dataclass(frozen=True, slots=True)
class Mark:
    """One marked feature: pixel position on the image (top-left origin), kind and optional label."""

    n: int
    x: int
    y: int
    kind: Kind
    label: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Report form of the mark."""
        return {"n": self.n, "x": self.x, "y": self.y, "kind": self.kind, "label": self.label}


@dataclass(frozen=True, slots=True)
class Annotation:
    """One annotation set as it stands in the custody log."""

    seq: int
    ts_utc: str
    actor: str
    job_id: str
    sha256: str  # the output image the marks are on
    role: str
    width: int
    height: int
    marks: tuple[Mark, ...]
    note: str | None = None
    replaces: int | None = None
    signed_seq: int | None = None  # the chain.sign entry appended right after it, when known

    def to_json(self) -> dict[str, Any]:
        """Report form of the set."""
        return {
            "seq": self.seq,
            "ts_utc": self.ts_utc,
            "actor": self.actor,
            "job_id": self.job_id,
            "sha256": self.sha256,
            "role": self.role,
            "image": {"width": self.width, "height": self.height},
            "marks": [m.to_json() for m in self.marks],
            "note": self.note,
            "replaces": self.replaces,
            "signed_seq": self.signed_seq,
        }


def _clean(text: object, what: str, limit: int) -> str | None:
    if text is None:
        return None
    if not isinstance(text, str):
        raise ParameterError(f"{what} must be text")
    text = text.replace("\r\n", "\n").strip()
    if text == "":
        return None
    if len(text) > limit or _REFUSED.search(text.replace("\n", "") if what == "note" else text):
        raise ParameterError(f"{what} must be 1-{limit} printable characters")
    return text


def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG header (the stored outputs are PNG)."""
    if len(data) < 24 or not data.startswith(_PNG) or data[12:16] != b"IHDR":
        raise ParameterError("the annotated image must be a stored PNG output")
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def check_marks(raw: object, width: int, height: int) -> tuple[Mark, ...]:
    """Validate marks from the examiner (CLI, sidecar): whole pixels inside the image, allowed kinds, short labels."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_MARKS:
        raise ParameterError(f"marks must be a list of 1-{MAX_MARKS} marks")
    marks: list[Mark] = []
    for n, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ParameterError(f"mark {n} must be an object")
        x, y, kind = item.get("x"), item.get("y"), item.get("kind")
        if not (isinstance(x, int) and isinstance(y, int)) or isinstance(x, bool) or isinstance(y, bool):
            raise ParameterError(f"mark {n}: x and y must be whole pixels")
        if not (0 <= x < width and 0 <= y < height):
            raise ParameterError(f"mark {n}: ({x}, {y}) lies outside the {width} x {height} image")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ParameterError(f"mark {n}: kind must be one of {', '.join(KINDS)}")
        unknown = set(item) - {"x", "y", "kind", "label", "n"}
        if unknown:
            raise ParameterError(f"mark {n}: unknown field(s) {', '.join(sorted(map(str, unknown)))}")
        marks.append(Mark(n, x, y, cast(Kind, kind), _clean(item.get("label"), f"mark {n} label", MAX_LABEL)))
    return tuple(marks)


def _annotation(entry: Entry, signed_seq: int | None) -> Annotation:
    marks = tuple(
        Mark(int(m["n"]), int(m["x"]), int(m["y"]), cast(Kind, m["kind"]), m.get("label")) for m in entry["marks"]
    )
    image = entry["image"]
    return Annotation(
        seq=int(entry["seq"]),
        ts_utc=str(entry["ts_utc"]),
        actor=str(entry["actor"]),
        job_id=str(entry["job_id"]),
        sha256=str(entry["sha256"]),
        role=str(image["role"]),
        width=int(image["width"]),
        height=int(image["height"]),
        marks=marks,
        note=entry.get("note"),
        replaces=entry.get("replaces"),
        signed_seq=signed_seq,
    )


def list_annotations(
    entries: Iterable[Entry], *, job_id: str | None = None, sha256: str | None = None
) -> list[Annotation]:
    """Return every set in log order with the seq of the signature that followed it, or those of one job or image."""
    found: list[Annotation] = []
    pending: Annotation | None = None
    for entry in entries:
        if pending is not None and entry["action"] == "chain.sign":
            found[-1] = replace(pending, signed_seq=int(entry["seq"]))
            pending = None
        if entry["action"] == ACTION and entry["result"] == "ok":
            pending = _annotation(entry, None)
            found.append(pending)
    return [a for a in found if (job_id is None or a.job_id == job_id) and (sha256 is None or a.sha256 == sha256)]


def current_annotations(entries: Iterable[Entry], *, job_id: str | None = None) -> list[Annotation]:
    """Return the sets that no later set replaced."""
    sets = list_annotations(entries, job_id=job_id)
    replaced = {a.replaces for a in sets if a.replaces is not None}
    return [a for a in sets if a.seq not in replaced]


def add_annotation(
    case: OpenCase,
    signer: Signer,
    *,
    job_id: str,
    sha256: str,
    marks: object,
    note: str | None = None,
    replaces: int | None = None,
) -> Annotation:
    """Record an annotation set on one output image of `job_id` and sign the chain head right after it."""
    item = case.item(sha256)  # refuses an unknown or ambiguous item
    if item.role not in IMAGE_ROLES or item.job_id != job_id:
        raise ParameterError("annotations go on a print or comparison export image of the same job")
    width, height = _png_size(case.read(item.sha256, job_id=job_id))  # a logged read of the output
    checked = check_marks(marks, width, height)
    clean_note = _clean(note, "note", MAX_NOTE)
    if replaces is not None:
        earlier = next((a for a in list_annotations(case.entries) if a.seq == replaces), None)
        if earlier is None or earlier.sha256 != item.sha256:
            raise ParameterError(f"custody entry {replaces} is not an annotation set of this image")
    entry = case.custody.append(
        ACTION,
        job_id=job_id,
        sha256=item.sha256,
        image={"role": item.role, "width": width, "height": height},
        marks=[m.to_json() for m in checked],
        note=clean_note,
        replaces=replaces,
    )
    case.entries.append(entry)
    signed = case.custody.sign_head(signer)  # the set is covered by a signature at once
    case.entries.append(signed)
    return _annotation(entry, int(signed["seq"]))
