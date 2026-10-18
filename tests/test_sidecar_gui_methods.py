"""Sidecar methods added for the desktop GUI: identity status, case info, legal hold, region previews."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from ridge.case.identity import create_identity
from ridge.case.limits import FILE as LIMITS_FILE
from ridge.case.limits import SCHEMA as LIMITS_SCHEMA
from ridge.case.processing_record import check_exported_log
from ridge.sidecar.handlers import METHODS, Session
from ridge.sidecar.protocol import APPLICATION_ERROR, INVALID_PARAMS
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


def call(session: Session, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message = {"jsonrpc": "2.0", "id": 1, "method": method, **({"params": params} if params is not None else {})}
    reply: dict[str, Any] = json.loads(handle(json.dumps(message).encode(), session))
    return reply


def result(reply: dict[str, Any]) -> Any:
    assert "result" in reply, reply
    return reply["result"]


def error_code(reply: dict[str, Any]) -> int:
    assert "error" in reply, reply
    return int(reply["error"]["code"])


def png_size(b64: str) -> tuple[int, int]:
    with Image.open(io.BytesIO(base64.b64decode(b64))) as image:
        return image.size


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def unlocked(tmp_path: Path, keystore: MemoryKeyStore) -> tuple[Session, Path]:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(store, keystore)
    session = Session(keystore_factory=lambda: keystore)
    result(call(session, "session.unlock", {"store": str(store), "case_id": case_dir.name, "passphrase": PASSPHRASE}))
    return session, case_dir


def test_identity_status_tells_first_run_from_an_existing_store(tmp_path: Path, keystore: MemoryKeyStore) -> None:
    session = Session(keystore_factory=lambda: keystore)
    store = (tmp_path / "store").resolve()
    assert result(call(session, "store.identity", {"store": str(store)})) == {"exists": False}
    signer = create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    shown = result(call(session, "store.identity", {"store": str(store)}))
    assert (shown["exists"], shown["key_id"]) == (True, signer.key_id)
    assert base64.b64decode(shown["public_key"]) == signer.public_key
    assert error_code(call(session, "store.identity", {"store": "relative"})) == APPLICATION_ERROR


def test_identity_status_refuses_a_tampered_identity(tmp_path: Path, keystore: MemoryKeyStore) -> None:
    store = (tmp_path / "store").resolve()
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    record = json.loads((store / "identity.json").read_text(encoding="utf-8"))
    record["key_id"] = "0" * 16
    (store / "identity.json").write_text(json.dumps(record), encoding="utf-8")
    reply = call(Session(keystore_factory=lambda: keystore), "store.identity", {"store": str(store)})
    assert error_code(reply) == APPLICATION_ERROR


def test_case_info_and_legal_hold(unlocked: tuple[Session, Path]) -> None:
    session, case_dir = unlocked
    shown = result(call(session, "case.info"))
    assert (shown["case_id"], shown["reference"], shown["legal_hold"]) == (case_dir.name, "KT-2026-0001", False)
    assert shown["legal_basis"] == "Synthetic test basis"
    placed = result(call(session, "case.hold", {"on": True, "reason": "Court order 12/2026"}))
    assert placed["legal_hold"] is True
    assert result(call(session, "case.info"))["legal_hold"] is True
    entries = session.case.entries if session.case else []
    assert entries[-1]["action"] == "case.hold"
    for bad in ({"on": True, "reason": ""}, {"on": True, "reason": "x\x07y"}):
        assert error_code(call(session, "case.hold", bad)) == APPLICATION_ERROR
    assert error_code(call(session, "case.hold", {"on": 1, "reason": "r"})) == INVALID_PARAMS
    assert result(call(session, "case.hold", {"on": False, "reason": "Order lifted"}))["legal_hold"] is False


def test_a_hold_in_an_open_session_keeps_verify_and_records_intact(
    unlocked: tuple[Session, Path], tmp_path: Path
) -> None:
    session, _ = unlocked
    result(call(session, "case.hold", {"on": True, "reason": "Court order 12/2026"}))
    assert result(call(session, "case.verify"))["ok"] is True
    record = (tmp_path / "record.json").resolve()
    logged = result(call(session, "log.export", {"dest": str(record)}))
    checked = check_exported_log(record, expected_key_id=logged["key_id"])
    assert checked.entries == logged["entries"]


def test_case_methods_refuse_a_locked_session(keystore: MemoryKeyStore) -> None:
    session = Session(keystore_factory=lambda: keystore)
    for method, params in (("case.info", {}), ("case.hold", {"on": True, "reason": "r"})):
        assert error_code(call(session, method, params)) == APPLICATION_ERROR


def test_preview_reports_the_source_size(unlocked: tuple[Session, Path], tmp_path: Path) -> None:
    session, _ = unlocked
    photo = photo_file(tmp_path / "in")
    with Image.open(photo) as image:
        width, height = image.size
    evidence = result(call(session, "case.import", {"path": str(photo.resolve())}))
    shown = result(call(session, "preview.get", {"sha256": evidence["sha256"], "max_side": 64}))
    assert (shown["source_width"], shown["source_height"]) == (width, height)
    assert max(png_size(shown["png_base64"])) <= 64


def test_region_previews_are_unscaled_and_clipped(unlocked: tuple[Session, Path], tmp_path: Path) -> None:
    session, _ = unlocked
    pixels = np.arange(200 * 120, dtype=np.uint32).reshape(120, 200) % 251
    path = tmp_path / "gradient.png"
    Image.fromarray(pixels.astype(np.uint8)).save(path)
    sha = result(call(session, "case.import", {"path": str(path.resolve())}))["sha256"]
    region = result(call(session, "preview.region", {"sha256": sha, "x": 10, "y": 20, "width": 30, "height": 40}))
    assert (region["width"], region["height"], region["source_width"], region["source_height"]) == (30, 40, 200, 120)
    with Image.open(io.BytesIO(base64.b64decode(region["png_base64"]))) as image:
        got = np.asarray(image.convert("L"))
    assert np.array_equal(got, pixels[20:60, 10:40].astype(np.uint8))  # full resolution, no resampling
    edge = result(call(session, "preview.region", {"sha256": sha, "x": 190, "y": 100, "width": 64, "height": 64}))
    assert (edge["width"], edge["height"]) == (10, 20)
    reads = [e for e in (session.case.entries if session.case else []) if e["action"] == "evidence.read"]
    assert len(reads) == 2  # every display read is logged (FR-22)


@pytest.mark.parametrize(
    "region",
    [
        {"x": -1, "y": 0, "width": 10, "height": 10},
        {"x": 0, "y": 0, "width": 0, "height": 10},
        {"x": 0, "y": 0, "width": 4096, "height": 10},
        {"x": 500, "y": 0, "width": 10, "height": 10},
        {"x": 0, "y": 500, "width": 10, "height": 10},
    ],
)
def test_bad_regions_are_refused(unlocked: tuple[Session, Path], tmp_path: Path, region: dict[str, int]) -> None:
    session, _ = unlocked
    sha = result(call(session, "case.import", {"path": str(photo_file(tmp_path / "in").resolve())}))["sha256"]
    assert error_code(call(session, "preview.region", {"sha256": sha, **region})) == APPLICATION_ERROR


def test_region_parameters_are_typed(unlocked: tuple[Session, Path]) -> None:
    session, _ = unlocked
    params = {"sha256": "a" * 64, "x": 0.5, "y": 0, "width": 10, "height": 10}
    assert error_code(call(session, "preview.region", params)) == INVALID_PARAMS
    assert error_code(call(session, "preview.region", {"sha256": "a" * 64})) == INVALID_PARAMS


def test_every_method_has_a_schema() -> None:
    assert {"store.identity", "case.info", "case.hold", "preview.region"} <= set(METHODS)
    for name, (handler, schema) in METHODS.items():
        assert callable(handler), name
        assert isinstance(schema, dict), name


def test_store_limits_of_use(tmp_path: Path, keystore: MemoryKeyStore) -> None:
    session = Session(keystore_factory=lambda: keystore)
    store = (tmp_path / "store").resolve()
    store.mkdir()
    assert result(call(session, "store.limits", {"store": str(store)})) == {"configured": False}
    (store / LIMITS_FILE).write_text(
        json.dumps({"schema": LIMITS_SCHEMA, "source": "VR-2027-01", "min_nfiq2": 30}), encoding="utf-8"
    )
    shown = result(call(session, "store.limits", {"store": str(store)}))
    assert (shown["configured"], shown["source"], shown["limits"]) == (True, "VR-2027-01", {"min_nfiq2": 30.0})
    (store / LIMITS_FILE).write_text("{", encoding="utf-8")
    assert error_code(call(session, "store.limits", {"store": str(store)})) == APPLICATION_ERROR


def test_minutiae_for_the_overlay_and_limits_in_job_results(unlocked: tuple[Session, Path], tmp_path: Path) -> None:
    session, case_dir = unlocked
    (case_dir.parent / LIMITS_FILE).write_text(
        json.dumps({"schema": LIMITS_SCHEMA, "source": "VR-2027-01", "min_ridge_period_px": 500}), encoding="utf-8"
    )
    evidence = result(call(session, "case.import", {"path": str(photo_file(tmp_path / "in").resolve())}))
    job = result(call(session, "job.run", {"evidence": evidence["sha256"], "minutiae": True}))
    assert job["limits_of_use"]["within"] is False
    found = next(o for o in job["outputs"] if o["role"] == "minutiae")
    shown = result(call(session, "minutiae.get", {"sha256": found["sha256"]}))
    assert shown["label"].startswith("unvalidated")
    assert shown["print"]["width"] > 0
    assert shown["export"]["width"] > 0
    assert len(shown["print"]["minutiae"]) == job["minutiae"]["count"]
    printed = next(o for o in job["outputs"] if o["role"] == "print")
    assert error_code(call(session, "minutiae.get", {"sha256": printed["sha256"]})) == APPLICATION_ERROR
    reads = [e for e in (session.case.entries if session.case else []) if e["action"] == "minutiae.read"]
    assert len(reads) == 1  # the overlay read is logged (FR-22)
