"""Side-by-side comparison sheet (PRD FR-52): a Ridge export beside an imported NAFIS/AFIS reference.

This is a view aid only. Ridge does not align, match or score anything. Both images are resampled
to one resolution, so a millimetre has the same length on both sides, and each gets a 10 mm scale
bar. The export's resolution is the one its job wrote into the PNG. The reference's resolution
comes from its file (PNG pHYs, JPEG or TIFF density) or from the examiner. If neither gives a
plausible fingerprint resolution, the sheet is refused rather than guessed: a 72 or 96 ppi value
is a software default, not a scan resolution.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import cv2
import numpy as np
from PIL import Image

from ridge.arrays import ImageU8
from ridge.case.case_model import publish_logged
from ridge.case.crypto import sha256_hex
from ridge.case.store import OpenCase
from ridge.errors import IntegrityError, OutputExistsError, ParameterError
from ridge.export.png import encode_png
from ridge.export.validate import finite
from ridge.image_io import ALLOWED_FORMATS, ReadLimits, decode_image

SHEET_PPI: Final = 500.0
PLAUSIBLE_PPI: Final = (250.0, 2000.0)  # fingerprint scans and AFIS images; outside this a value is a default
MAX_SHEET_PIXELS: Final = 100_000_000
GAP_MM, BAR_MM = 5.0, 10.0
DISCLAIMER: Final = "View aid only. Ridge does not match, align or identify. Conclusions rest with the examiner."


@dataclass(frozen=True)
class Sheet:
    """A rendered comparison sheet and what it was made from."""

    png: bytes
    sha256: str
    ppi: float
    export_sha256: str
    reference_sha256: str
    reference_ppi: float
    reference_ppi_source: str  # "file" or "examiner"


def file_ppi(data: bytes) -> float | None:
    """Return the resolution an image file declares, or None when it declares none or two different ones."""
    with Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS) as im:
        dpi = im.info.get("dpi")
    if not dpi:
        return None
    x, y = float(dpi[0]), float(dpi[1])
    # PNG stores whole pixels per metre (1000 ppi reads back as 999.998): 0.1 ppi is the honest precision.
    return round(x, 1) if x > 0 and abs(x - y) <= 0.01 * x else None


def plausible_ppi(value: object, name: str) -> float:
    """Return `value` if it is a plausible fingerprint resolution, else raise ParameterError."""
    ppi = finite(value, name)
    low, high = PLAUSIBLE_PPI
    if not low <= ppi <= high:
        raise ParameterError(f"{name} {ppi:g} is not a fingerprint resolution ({low:g}-{high:g} ppi)")
    return ppi


def build_sheet(
    case: OpenCase, export_ref: str, reference_ref: str, *, reference_ppi: float | None = None, ppi: float = SHEET_PPI
) -> Sheet:
    """Render the sheet for one export and one reference (both reads are logged)."""
    export, reference = case.item(export_ref), case.item(reference_ref)
    if export.role != "export":
        raise ParameterError(f"{export.sha256[:12]} is a {export.role} item, not a comparison export")
    if reference.role != "reference":
        raise ParameterError(f"{reference.sha256[:12]} is a {reference.role} item, not an imported reference")
    ppi = plausible_ppi(ppi, "sheet resolution")
    export_data, reference_data = case.read(export.sha256), case.read(reference.sha256)
    export_ppi = file_ppi(export_data)
    if export_ppi is None:
        raise IntegrityError(f"export {export.sha256[:12]} has lost its resolution metadata")
    if reference_ppi is None:
        declared = file_ppi(reference_data)
        if declared is None:
            raise ParameterError("the reference declares no resolution: give it (e.g. --reference-ppi 500)")
        ref_ppi, source = plausible_ppi(declared, "the reference's declared resolution"), "file"
    else:
        ref_ppi, source = plausible_ppi(reference_ppi, "reference resolution"), "examiner"

    left = _resample(_gray(export_data), export_ppi / ppi)
    right = _resample(_gray(reference_data), ref_ppi / ppi)
    captions = (
        (f"Ridge export {export.sha256[:12]}", f"{_ascii(export.label)}; job {(export.job_id or '?')[:8]}"),
        (
            f"Reference {reference.sha256[:12]}",
            f"{_ascii(reference.label)}; {ref_ppi:g} ppi from {source}; {_ascii(reference.source or '')}",
        ),
    )
    png = encode_png(_compose(left, right, ppi, captions), ppi)
    return Sheet(png, sha256_hex(png), ppi, export.sha256, reference.sha256, ref_ppi, source)


def export_sheet(
    case: OpenCase,
    export_ref: str,
    reference_ref: str,
    dest: Path,
    *,
    reference_ppi: float | None = None,
    ppi: float = SHEET_PPI,
    overwrite: bool = False,
) -> Sheet:
    """Write the sheet to `dest` in plaintext (logged as ``comparison.export``)."""
    if not overwrite and dest.exists():
        raise OutputExistsError(f"{dest.name} already exists (use --overwrite to replace)")
    sheet = build_sheet(case, export_ref, reference_ref, reference_ppi=reference_ppi, ppi=ppi)
    publish_logged(
        [(dest, sheet.png)],
        lambda: case.entries.append(
            case.custody.append(
                "comparison.export",
                sha256=sheet.sha256,
                export_sha256=sheet.export_sha256,
                reference_sha256=sheet.reference_sha256,
                reference_ppi=sheet.reference_ppi,
                reference_ppi_source=sheet.reference_ppi_source,
                ppi=sheet.ppi,
                destination=str(dest.resolve()),
            )
        ),
        overwrite=overwrite,
    )
    return sheet


def _gray(data: bytes) -> ImageU8:
    return cast(ImageU8, cv2.cvtColor(decode_image(data, ReadLimits()), cv2.COLOR_BGR2GRAY))


def _resample(image: ImageU8, shrink: float) -> ImageU8:
    """Resize by 1/`shrink` (shrink > 1 makes the image smaller)."""
    if abs(shrink - 1.0) < 1e-3:
        return image
    h, w = image.shape
    size = (max(1, round(w / shrink)), max(1, round(h / shrink)))
    if size[0] * size[1] > MAX_SHEET_PIXELS:
        raise ParameterError("the comparison sheet would be too large; use a lower sheet resolution")
    method = cv2.INTER_AREA if shrink > 1 else cv2.INTER_CUBIC
    return cast(ImageU8, cv2.resize(image, size, interpolation=method))


def _ascii(text: str, limit: int = 48) -> str:
    """Printable ASCII for the burnt-in captions (Hershey fonts have no other glyphs)."""
    clean = "".join(c if " " <= c <= "~" else "?" for c in text)
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


def _text_width(text: str, scale: float) -> int:
    return int(cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0])


def _compose(left: ImageU8, right: ImageU8, ppi: float, captions: tuple[tuple[str, str], ...]) -> ImageU8:
    px_per_mm = ppi / 25.4
    font_scale = 0.6 * ppi / SHEET_PPI
    line = max(12, round(28 * ppi / SHEET_PPI))
    margin, gap, bar = line, round(GAP_MM * px_per_mm), round(BAR_MM * px_per_mm)
    top = margin + 2 * line
    body = max(left.shape[0], right.shape[0])
    columns = [
        max(image.shape[1], bar, _text_width(title, font_scale), _text_width(detail, font_scale * 0.8))
        for image, (title, detail) in zip((left, right), captions, strict=True)
    ]
    width = max(2 * margin + sum(columns) + gap, 2 * margin + _text_width(DISCLAIMER, font_scale))
    height = top + body + 3 * line + margin
    if width * height > MAX_SHEET_PIXELS:
        raise ParameterError("the comparison sheet would be too large; use a lower sheet resolution")
    sheet = np.full((height, width), 255, dtype=np.uint8)
    x = margin
    for image, (title, detail), column in zip((left, right), captions, columns, strict=True):
        h, w = image.shape
        sheet[top : top + h, x : x + w] = image
        cv2.putText(sheet, title, (x, margin + line // 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, 0, 1, cv2.LINE_AA)
        cv2.putText(sheet, detail, (x, margin + line + line // 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.8, 0, 1)
        bar_y = top + body + line // 2
        cv2.rectangle(sheet, (x, bar_y), (x + bar, bar_y + max(2, line // 5)), 0, thickness=-1)
        cv2.putText(sheet, "10 mm", (x, bar_y + line), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.8, 0, 1)
        x += column + gap
    cv2.putText(sheet, DISCLAIMER, (margin, height - margin), cv2.FONT_HERSHEY_SIMPLEX, font_scale, 0, 1, cv2.LINE_AA)
    return cast(ImageU8, sheet)
