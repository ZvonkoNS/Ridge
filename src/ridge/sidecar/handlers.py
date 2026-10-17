"""Sidecar methods: thin adapters from validated JSON-RPC params to the case-store API.

The sidecar is a trusted layer (architecture §5, ADR-002); its caller is the Tauri Rust core,
which forwards only allow-listed commands from the untrusted WebView. Every argument is still
validated here (deny by default): case ids must be UUIDs (no path traversal), paths absolute,
numbers in range. ``identity.create``, ``case.create`` and ``session.unlock`` carry the examiner
passphrase and must only ever be sent by the Rust core from a native dialog, never from
WebView code.
"""

from __future__ import annotations

import base64
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

import cv2

import ridge
from ridge.arrays import ImageU8
from ridge.case.export_step import ExportOptions
from ridge.case.identity import Signer, create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.keys import KdfParams, KeyringKeyStore, KeyStore, b64
from ridge.case.store import OpenCase, StoredItem, create_case, open_case
from ridge.case.verify import verify_case
from ridge.errors import CaseError, ParameterError
from ridge.image_io import ReadLimits, decode_image, encode_image
from ridge.sidecar.protocol import Json, Schema

PROTOCOL = "ridge.sidecar/1"
DEFAULT_IDLE_TIMEOUT_S = 15 * 60.0
PREVIEW_DEFAULT, PREVIEW_MAX = 1024, 2048
NUMBER = (int, float)


@dataclass
class Session:
    """At most one unlocked case per sidecar process, locked again after `idle_timeout_s`."""

    keystore_factory: Callable[[], KeyStore] = KeyringKeyStore
    kdf_params: KdfParams = field(default_factory=KdfParams)  # Argon2id cost for new identities and cases
    idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S
    clock: Callable[[], float] = time.monotonic
    case: OpenCase | None = None
    signer: Signer | None = None
    store: Path | None = None
    last_activity: float = 0.0

    def touch(self) -> None:
        """Lock first if the session sat idle too long, then record activity."""
        now = self.clock()
        if self.case is not None and now - self.last_activity > self.idle_timeout_s:
            self.close()  # an unattended workstation must not keep a decrypted case open
        self.last_activity = now

    def require(self) -> tuple[OpenCase, Signer]:
        """Return the unlocked case and identity, or refuse."""
        if self.case is None or self.signer is None:
            raise CaseError("no case is unlocked")
        return self.case, self.signer

    def close(self) -> None:
        """Lock the case (releases the case lock); forget the signing key."""
        if self.case is not None:
            self.case.close()
        self.case, self.signer, self.store = None, None, None


def _absolute(value: str, what: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "\0" in value:
        raise ParameterError(f"{what} must be an absolute path")
    return path


def _item(i: StoredItem) -> dict[str, Json]:
    return {"sha256": i.sha256, "role": i.role, "size": i.size, "label": i.label, "job_id": i.job_id}


def version(session: Session, params: dict[str, Json]) -> Json:
    """Ridge and protocol versions."""
    return {"ridge": ridge.__version__, "protocol": PROTOCOL}


def unlock(session: Session, params: dict[str, Json]) -> Json:
    """Open one case of a store with the examiner passphrase (sent by the Rust core only)."""
    store = _absolute(params["store"], "store")
    try:
        case_id = str(uuid.UUID(params["case_id"]))
    except ValueError:
        raise ParameterError("case_id must be a case UUID") from None
    session.close()
    keystore = session.keystore_factory()
    signer = unlock_identity(store, params["passphrase"], keystore)
    case = open_case(store / case_id, params["passphrase"], keystore)
    try:
        meta = case.meta()
    except BaseException:
        case.close()  # a case whose metadata cannot be read is never left unlocked (fail closed)
        raise
    session.case, session.signer, session.store = case, signer, store
    return {
        "case_id": case_id,
        "reference": meta.case_reference,
        "retention_until": meta.retention_until.isoformat(),
        "legal_hold": meta.legal_hold,
    }


def identity_create(session: Session, params: dict[str, Json]) -> Json:
    """Create the examiner signing identity of a store (first run; sent by the Rust core only)."""
    store = _absolute(params["store"], "store")
    signer = create_identity(store, params["passphrase"], session.keystore_factory(), session.kdf_params)
    return {"key_id": signer.key_id, "public_key": b64(signer.public_key)}


def case_create(session: Session, params: dict[str, Json]) -> Json:
    """Create a case protected by the identity's passphrase (sent by the Rust core only); unlock it next."""
    store = _absolute(params["store"], "store")
    try:
        retention = date.fromisoformat(params["retention_until"])
    except ValueError:
        raise ParameterError("retention_until must be a date, YYYY-MM-DD") from None
    keystore = session.keystore_factory()
    unlock_identity(store, params["passphrase"], keystore)  # one passphrase for identity and cases
    case_dir = create_case(
        store,
        case_reference=params["reference"],
        legal_basis=params["legal_basis"],
        retention_until=retention,
        passphrase=params["passphrase"],
        keystore=keystore,
        params=session.kdf_params,
    )
    return {"case_id": case_dir.name}


def status(session: Session, params: dict[str, Json]) -> Json:
    """Whether a case is unlocked, and the idle timeout."""
    return {"unlocked": session.case is not None, "idle_timeout_s": session.idle_timeout_s}


def lock(session: Session, params: dict[str, Json]) -> Json:
    """Lock the open case."""
    session.close()
    return {"locked": True}


def items(session: Session, params: dict[str, Json]) -> Json:
    """Everything stored in the case."""
    case, _ = session.require()
    return [_item(i) for i in case.items()]


def import_evidence(session: Session, params: dict[str, Json]) -> Json:
    """Import one evidence photo chosen in a native file dialog."""
    case, _ = session.require()
    return _item(case.import_evidence(_absolute(params["path"], "path")))


def run_job(session: Session, params: dict[str, Json]) -> Json:
    """Run one extraction job; returns the outputs and the report's summary fields."""
    case, signer = session.require()
    ruler = params.get("ruler")
    if ruler is not None and (
        len(ruler) != 5 or not all(isinstance(v, NUMBER) and not isinstance(v, bool) for v in ruler)
    ):
        raise ParameterError("ruler must be [x1, y1, x2, y2, millimetres]")
    export = ExportOptions(
        enabled=params.get("export", True),
        mirror=params.get("mirror", True),
        target_ppi=float(params.get("ppi", 500.0)),
        ruler=None if ruler is None else cast(tuple[float, float, float, float, float], tuple(float(v) for v in ruler)),
    )
    job = JobParams(
        period=params.get("period"),
        min_quality=float(params.get("min_quality", 0.25)),
        flip=params.get("flip", False),
        crop=params.get("crop", True),
        debug=params.get("debug", False),
        export=export,
        minutiae=params.get("minutiae", False),
    )
    outcome = run_extraction_job(case, params["evidence"], signer, job)
    report = outcome.report
    summary = {key: report.get(key) for key in ("measurements", "export", "quality", "minutiae")}
    return {"job_id": outcome.job_id, "outputs": [_item(o) for o in outcome.outputs], **summary}


def verify(session: Session, params: dict[str, Json]) -> Json:
    """Verify the open case."""
    case, _ = session.require()
    if session.store is None:  # pragma: no cover - set together with the case
        raise CaseError("no store")
    result = verify_case(case, session.store)
    return {"ok": result.ok, "problems": result.problems, "items": result.items, "reports": result.reports}


def export_item(session: Session, params: dict[str, Json]) -> Json:
    """Export one item to a path chosen in a native save dialog (logged)."""
    case, _ = session.require()
    dest = case.export(params["sha256"], _absolute(params["dest"], "dest"), overwrite=params.get("overwrite", False))
    return {"exported": str(dest)}


def preview(session: Session, params: dict[str, Json]) -> Json:
    """Return a bounded PNG preview of a stored image for display (the read is logged)."""
    case, _ = session.require()
    max_side = params.get("max_side", PREVIEW_DEFAULT)
    if not 16 <= max_side <= PREVIEW_MAX:
        raise ParameterError(f"max_side must be between 16 and {PREVIEW_MAX}")
    item = case.item(params["sha256"])
    if item.role == "minutiae":
        raise ParameterError("minutiae are JSON, not an image")
    image = decode_image(case.read(item.sha256), ReadLimits())
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        image = cast(
            ImageU8,
            cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA),
        )
    png = encode_image(image, ".png")
    return {
        "sha256": item.sha256,
        "width": image.shape[1],
        "height": image.shape[0],
        "png_base64": base64.b64encode(png).decode("ascii"),
    }


Handler = Callable[[Session, dict[str, Json]], Json]
str_ = (str,)
bool_ = (bool,)
METHODS: dict[str, tuple[Handler, Schema]] = {
    "ridge.version": (version, {}),
    "identity.create": (identity_create, {"store": (str_, True), "passphrase": (str_, True)}),
    "case.create": (
        case_create,
        {
            "store": (str_, True),
            "reference": (str_, True),
            "legal_basis": (str_, True),
            "retention_until": (str_, True),
            "passphrase": (str_, True),
        },
    ),
    "session.unlock": (unlock, {"store": (str_, True), "case_id": (str_, True), "passphrase": (str_, True)}),
    "session.lock": (lock, {}),
    "session.status": (status, {}),
    "case.items": (items, {}),
    "case.import": (import_evidence, {"path": (str_, True)}),
    "case.verify": (verify, {}),
    "case.export": (export_item, {"sha256": (str_, True), "dest": (str_, True), "overwrite": (bool_, False)}),
    "preview.get": (preview, {"sha256": (str_, True), "max_side": ((int,), False)}),
    "job.run": (
        run_job,
        {
            "evidence": (str_, True),
            "period": ((int, float, type(None)), False),
            "min_quality": (NUMBER, False),
            "flip": (bool_, False),
            "crop": (bool_, False),
            "debug": (bool_, False),
            "export": (bool_, False),
            "mirror": (bool_, False),
            "ppi": (NUMBER, False),
            "ruler": ((list, type(None)), False),
            "minutiae": (bool_, False),
        },
    ),
}
SCHEMAS: dict[str, Schema] = {name: schema for name, (_, schema) in METHODS.items()}
__all__ = ["METHODS", "SCHEMAS", "Session"]
