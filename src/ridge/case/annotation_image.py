"""Draw an annotation set on its image and export the result (FR-55).

The annotated image is a derived, plaintext file written outside the store with its custody entry
(`annotation.export`): the source image's hash, the set's seq and the written file's hash. It is never
a stored item and never replaces the output it was drawn on. Marks are drawn as outlines with their
numbers; the kinds and labels stay in the record, so nothing on the image needs a font beyond digits.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

from ridge.case.annotations import Annotation, list_annotations
from ridge.case.case_model import publish_logged
from ridge.case.store import OpenCase
from ridge.errors import ParameterError
from ridge.image_io import HARD_MAX_PIXELS

ACTION: Final = "annotation.export"
COLOUR: Final = (255, 72, 0)  # an orange-red that reads on the grey and on the black-and-white outputs
MIN_RADIUS: Final = 6


@dataclass(frozen=True, slots=True)
class ExportedAnnotation:
    """What was written: the set, the file and the hashes the custody entry names."""

    seq: int
    path: Path
    sha256: str  # the source image
    written_sha256: str
    marks: int


def _radius(width: int, height: int) -> int:
    return max(MIN_RADIUS, min(width, height) // 80)


def render_annotated(data: bytes, annotation: Annotation) -> bytes:
    """Return a PNG of the stored image with the set's marks drawn on it (outline plus number)."""
    with Image.open(BytesIO(data), formats=["PNG"]) as im:
        if im.width * im.height > HARD_MAX_PIXELS:
            raise ParameterError("the stored image is too large to annotate")
        if (im.width, im.height) != (annotation.width, annotation.height):
            raise ParameterError("the stored image no longer has the size the annotation set was made on")
        canvas = im.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    r = _radius(canvas.width, canvas.height)
    font = ImageFont.load_default(size=max(10, 2 * r))
    for mark in annotation.marks:
        x, y = mark.x, mark.y
        if mark.kind == "ending":
            draw.ellipse([x - r, y - r, x + r, y + r], outline=COLOUR, width=2)
        elif mark.kind == "bifurcation":
            draw.rectangle([x - r, y - r, x + r, y + r], outline=COLOUR, width=2)
        else:
            draw.polygon([(x, y - r), (x + r, y + r), (x - r, y + r)], outline=COLOUR, width=2)
        draw.text((x + r + 2, y - r), str(mark.n), fill=COLOUR, font=font)
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=False)
    return out.getvalue()


def export_annotated(case: OpenCase, seq: int, dest: Path, *, overwrite: bool = False) -> ExportedAnnotation:
    """Write the annotated image for the set at custody entry `seq` to `dest` (logged as ``annotation.export``)."""
    annotation = next((a for a in list_annotations(case.entries) if a.seq == seq), None)
    if annotation is None:
        raise ParameterError(f"custody entry {seq} is not an annotation set of this case")
    if dest.suffix.lower() != ".png":
        raise ParameterError("the annotated image is written as PNG; name the file .png")
    data = case.read(annotation.sha256, job_id=annotation.job_id)
    png = render_annotated(data, annotation)
    written = hashlib.sha256(png).hexdigest()

    def log() -> None:
        case.entries.append(
            case.custody.append(
                ACTION,
                annotation_seq=seq,  # the set's entry; `seq` itself is this entry's own number
                job_id=annotation.job_id,
                sha256=annotation.sha256,
                file=dest.name,
                written_sha256=written,
                marks=len(annotation.marks),
            )
        )

    publish_logged([(dest, png)], log, overwrite=overwrite)
    return ExportedAnnotation(seq, dest, annotation.sha256, written, len(annotation.marks))
