"""Sidecar methods on the unlocked case: metadata, legal hold, items, import, verify, export, previews.

Previews are for display only. Every preview decrypts and reads a stored image, so every preview
is a logged read (FR-22); images never leave the sidecar except as bounded PNGs.
"""

from __future__ import annotations

import base64
import json
from typing import cast

import cv2

from ridge.arrays import ImageU8
from ridge.case.compare import PLAUSIBLE_PPI, file_ppi
from ridge.case.export_step import MINUTIAE_LABEL
from ridge.case.notes import add_note, list_notes
from ridge.case.store import OpenCase, StoredItem
from ridge.case.verify import verify_case
from ridge.errors import ParameterError
from ridge.image_io import ReadLimits, decode_image, encode_image
from ridge.sidecar.protocol import Json
from ridge.sidecar.session import Session, absolute, item_json

PREVIEW_DEFAULT, PREVIEW_MAX = 1024, 2048
REGION_MAX_SIDE = 2048
MAX_MARKS = 5000  # far above any print; bounds the response


def info(session: Session, params: dict[str, Json]) -> Json:
    """Metadata of the unlocked case (decrypted from meta.enc)."""
    case, _ = session.require()
    meta = case.meta()
    return {
        "case_id": case.case_id,
        "reference": meta.case_reference,
        "legal_basis": meta.legal_basis,
        "retention_until": meta.retention_until.isoformat(),
        "legal_hold": meta.legal_hold,
    }


def hold(session: Session, params: dict[str, Json]) -> Json:
    """Place or lift a legal hold with the examiner's reason (logged as ``case.hold``)."""
    case, _ = session.require()
    case.set_legal_hold(params["on"], params["reason"])
    return info(session, {})


def note_add(session: Session, params: dict[str, Json]) -> Json:
    """Append an examiner note to the case, a job or a stored item (logged as ``examiner.note``)."""
    case, _ = session.require()
    note = add_note(
        case,
        params["text"],
        job_id=params.get("job_id"),
        sha256=params.get("sha256"),
        corrects=params.get("corrects"),
    )
    return note.to_json()


def notes(session: Session, params: dict[str, Json]) -> Json:
    """List the examiner notes of the case, or of one job."""
    case, _ = session.require()
    return [n.to_json() for n in list_notes(case.entries, job_id=params.get("job_id"))]


def items(session: Session, params: dict[str, Json]) -> Json:
    """Everything stored in the case."""
    case, _ = session.require()
    return [item_json(i) for i in case.items()]


def import_evidence(session: Session, params: dict[str, Json]) -> Json:
    """Import one evidence photo chosen in a native file dialog."""
    case, _ = session.require()
    return item_json(case.import_evidence(absolute(params["path"], "path"), source=params.get("source")))


def import_reference(session: Session, params: dict[str, Json]) -> Json:
    """Import a NAFIS/AFIS candidate image chosen in a native file dialog (view only)."""
    case, _ = session.require()
    return item_json(case.import_reference(absolute(params["path"], "path"), params["source"]))


def verify(session: Session, params: dict[str, Json]) -> Json:
    """Verify the open case."""
    case, _ = session.require()
    result = verify_case(case, session.require_store())
    return {"ok": result.ok, "problems": result.problems, "items": result.items, "reports": result.reports}


def export_item(session: Session, params: dict[str, Json]) -> Json:
    """Export one item to a path chosen in a native save dialog (logged)."""
    case, _ = session.require()
    dest = case.export(params["sha256"], absolute(params["dest"], "dest"), overwrite=params.get("overwrite", False))
    return {"exported": str(dest)}


def declared_ppi(data: bytes) -> float | None:
    """Return the resolution the file declares if it is a plausible fingerprint resolution, else None.

    72 or 96 ppi defaults and other implausible values are never passed on as a scale.
    """
    ppi = file_ppi(data)
    low, high = PLAUSIBLE_PPI
    return ppi if ppi is not None and low <= ppi <= high else None


def _image(case: OpenCase, sha: str) -> tuple[StoredItem, ImageU8, bytes]:
    """Decrypt (logged) and decode a stored image; minutiae are JSON and refused."""
    item = case.item(sha)
    if item.role == "minutiae":
        raise ParameterError("minutiae are JSON, not an image")
    data = case.read(item.sha256)
    return item, decode_image(data, ReadLimits()), data


def _png(image: ImageU8) -> str:
    return base64.b64encode(encode_image(image, ".png")).decode("ascii")


def preview(session: Session, params: dict[str, Json]) -> Json:
    """Return a bounded PNG preview of a stored image for display (the read is logged).

    `source_width` and `source_height` are the size of the full image after EXIF orientation: the
    coordinate space of a job's ``roi`` and ``ruler``, so the GUI can map clicks on the preview.
    `ppi` is the resolution the file declares when it is a plausible fingerprint resolution
    (exports carry 500 ppi; scanned references often declare theirs), otherwise None.
    """
    case, _ = session.require()
    max_side = params.get("max_side", PREVIEW_DEFAULT)
    if not 16 <= max_side <= PREVIEW_MAX:
        raise ParameterError(f"max_side must be between 16 and {PREVIEW_MAX}")
    item, image, data = _image(case, params["sha256"])
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        image = cast(
            ImageU8,
            cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA),
        )
    return {
        "sha256": item.sha256,
        "width": image.shape[1],
        "height": image.shape[0],
        "source_width": w,
        "source_height": h,
        "ppi": declared_ppi(data),
        "png_base64": _png(image),
    }


def preview_region(session: Session, params: dict[str, Json]) -> Json:
    """Return a rectangle of a stored image at full resolution, unscaled, for pixel inspection.

    The rectangle starts inside the image and is clipped at its edges; each side is at most
    REGION_MAX_SIDE pixels. The read is logged like any other.
    """
    case, _ = session.require()
    x, y, width, height = (params[k] for k in ("x", "y", "width", "height"))
    if min(x, y) < 0 or not (1 <= width <= REGION_MAX_SIDE and 1 <= height <= REGION_MAX_SIDE):
        raise ParameterError(f"region must start at x, y >= 0 and be 1-{REGION_MAX_SIDE} pixels per side")
    item, image, _ = _image(case, params["sha256"])
    h, w = image.shape[:2]
    if x >= w or y >= h:
        raise ParameterError(f"region starts outside the {w} x {h} image")
    crop = image[y : min(h, y + height), x : min(w, x + width)].copy()
    return {
        "sha256": item.sha256,
        "x": x,
        "y": y,
        "width": crop.shape[1],
        "height": crop.shape[0],
        "source_width": w,
        "source_height": h,
        "png_base64": _png(crop),
    }


def _space(doc: object) -> Json:
    """One coordinate space of a minutiae artefact (print or export), or None."""
    if not isinstance(doc, dict) or not isinstance(doc.get("image"), dict):
        return None
    found = doc.get("minutiae")
    return {
        "width": doc["image"].get("width"),
        "height": doc["image"].get("height"),
        "ridge_period_px": doc.get("ridge_period_px"),
        "minutiae": found[:MAX_MARKS] if isinstance(found, list) else [],
    }


def minutiae(session: Session, params: dict[str, Json]) -> Json:
    """Return a job's minutiae in print and export space for the viewer overlay (the read is logged).

    The artefact was written by Ridge and its hash is checked on read; the overlay is drawn for
    orientation only and is labelled unvalidated (FR-40, profile exception).
    """
    case, _ = session.require()
    item = case.item(params["sha256"])
    if item.role != "minutiae":
        raise ParameterError("not a minutiae item")
    doc = json.loads(case.read(item.sha256).decode("utf-8"))
    return {
        "sha256": item.sha256,
        "job_id": item.job_id,
        "label": MINUTIAE_LABEL,
        "print": _space(doc),
        "export": _space(doc.get("export_space") if isinstance(doc, dict) else None),
    }
