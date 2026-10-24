"""Case store, custody chain, signed jobs, verification and disposal (PRD FR-20 to FR-27)."""

from __future__ import annotations

import base64
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rfc8785

from ridge import extract_fingerprint
from ridge.case.dispose import dispose_case
from ridge.case.identity import create_identity, unlock_identity, verify_signature
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.keys import unb64
from ridge.case.store import create_case, open_case
from ridge.case.verify import verify_case
from ridge.errors import (
    CaseError,
    CaseLockedError,
    ExtractionError,
    InputRejectedError,
    IntegrityError,
    KeyCustodyError,
    OutputExistsError,
    ParameterError,
    RetentionError,
)
from ridge.image_io import load_image
from tests.case_helpers import ACTOR, FAST_KDF, PASSPHRASE, MemoryKeyStore, future, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def all_bytes(folder: Path) -> bytes:
    return b"".join(p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file())


# ---------------------------------------------------------------- create / open


@pytest.mark.parametrize(
    ("reference", "basis", "retention"),
    [("", "basis", None), ("ref\x07", "basis", None), ("ref", "", None), ("ref", "basis", date(2020, 1, 1))],
)
def test_create_requires_reference_basis_and_future_retention(
    tmp_path: Path, keystore: MemoryKeyStore, reference: str, basis: str, retention: date | None
) -> None:
    with pytest.raises(ParameterError):
        create_case(
            tmp_path,
            case_reference=reference,
            legal_basis=basis,
            retention_until=retention or future(),
            passphrase=PASSPHRASE,
            keystore=keystore,
            params=FAST_KDF,
        )
    assert list(tmp_path.iterdir()) == []


def test_metadata_is_encrypted(case_dir: Path, keystore: MemoryKeyStore) -> None:
    assert b"KT-2026-0001" not in all_bytes(case_dir)
    assert b"Synthetic test basis" not in all_bytes(case_dir)
    with open_case(case_dir, PASSPHRASE, keystore, ACTOR) as case:
        assert case.meta().case_reference == "KT-2026-0001"
        assert case.entries[0]["action"] == "case.create"


def test_wrong_passphrase_or_account_is_denied(case_dir: Path, keystore: MemoryKeyStore) -> None:
    with pytest.raises(KeyCustodyError, match="wrong passphrase"):
        open_case(case_dir, PASSPHRASE + "x", keystore)
    with pytest.raises(KeyCustodyError):
        open_case(case_dir, PASSPHRASE, MemoryKeyStore())
    assert not (case_dir / "LOCK").exists()


@pytest.mark.parametrize(
    "change",
    [
        lambda r: b"{",
        lambda r: bytes([0xFF, 0xFE]),  # not UTF-8
        lambda r: json.dumps({k: v for k, v in r.items() if k != "salt"}).encode(),
        lambda r: json.dumps({**r, "wrapped_dek": 5}).encode(),
        lambda r: json.dumps({**r, "salt": "not base64!"}).encode(),
        lambda r: json.dumps({k: v for k, v in r.items() if k != "kdf"}).encode(),
        lambda r: json.dumps({**r, "pad": "x" * 70_000}).encode(),  # over the size bound
    ],
)
def test_a_malformed_case_file_is_refused_cleanly(case_dir: Path, keystore: MemoryKeyStore, change: Any) -> None:
    record = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    (case_dir / "case.json").write_bytes(change(record))
    with pytest.raises(IntegrityError, match="is malformed"):
        open_case(case_dir, PASSPHRASE, keystore)
    assert not (case_dir / "LOCK").exists()


def test_single_writer_lock(case_dir: Path, keystore: MemoryKeyStore) -> None:
    with open_case(case_dir, PASSPHRASE, keystore), pytest.raises(CaseLockedError):
        open_case(case_dir, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore):  # released after the first one closed
        pass


# ---------------------------------------------------------------- evidence


def test_import_is_hashed_encrypted_and_leaves_the_source_alone(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path
) -> None:
    src = photo_file(tmp_path / "in")
    before = (src.read_bytes(), src.stat().st_mtime_ns)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        item = case.import_evidence(src)
        again = case.import_evidence(src)
        assert again == item
        assert [i.sha256 for i in case.items()] == [item.sha256]
        assert case.entries[-1]["result"] == "duplicate"
        assert case.read(item.sha256) == src.read_bytes()
    assert (src.read_bytes(), src.stat().st_mtime_ns) == before
    stored = all_bytes(case_dir)
    assert src.read_bytes()[100:200] not in stored  # no plaintext pixels on disk
    assert item.sha256 not in "".join(p.name for p in case_dir.rglob("*"))  # names are keyed


def test_non_images_are_not_imported(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    bad = tmp_path / "notes.jpg"
    bad.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n")
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        with pytest.raises(InputRejectedError):
            case.import_evidence(bad)
        assert case.items() == []


def test_export_is_the_logged_plaintext_path(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    src = photo_file(tmp_path / "in")
    dest = tmp_path / "out" / "copy.png"
    dest.parent.mkdir()
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        item = case.import_evidence(src)
        case.export(item.sha256[:12], dest)
        assert dest.read_bytes() == src.read_bytes()
        with pytest.raises(OutputExistsError):
            case.export(item.sha256, dest)
        assert case.entries[-1]["action"] == "artefact.export"
        assert case.entries[-1]["destination"] == str(dest.resolve())


# ---------------------------------------------------------------- custody chain


def tamper_line(case_dir: Path, index: int, how: str) -> None:
    path = case_dir / "custody.jsonl.enc"
    lines = path.read_bytes().splitlines(keepends=True)
    if how == "flip":
        blob = bytearray(base64.b64decode(lines[index].strip()))
        blob[-1] ^= 1
        lines[index] = base64.b64encode(bytes(blob)) + b"\n"
    elif how == "delete":
        del lines[index]
    elif how == "swap":
        lines[index], lines[index + 1] = lines[index + 1], lines[index]
    path.write_bytes(b"".join(lines))


@pytest.mark.parametrize("how", ["flip", "delete", "swap"])
def test_custody_tampering_is_detected(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, how: str) -> None:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        case.import_evidence(photo_file(tmp_path / "a"))
        case.set_legal_hold(True, "test")
        case.set_legal_hold(False, "test")
    tamper_line(case_dir, 1, how)
    with pytest.raises(IntegrityError, match="custody log"):
        open_case(case_dir, PASSPHRASE, keystore)
    assert not (case_dir / "LOCK").exists()


# ---------------------------------------------------------------- jobs and reports


def test_job_is_reproducible_signed_and_complete(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    src = photo_file(tmp_path / "in")
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(src)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams(debug=True))
        canonical, signature = case.get_report(outcome.job_id)
        print_png = case.read(outcome.outputs[0].sha256, log=False)
    report = json.loads(canonical)
    assert canonical == bytes(rfc8785.dumps(report))
    assert verify_signature(unb64(report["signer"]["public_key"]), signature, canonical)
    assert report["input"]["sha256"] == evidence.sha256
    assert report["input"]["format"] == "PNG"
    export_params = {"enabled": True, "mirror": True, "target_ppi": 500, "ruler": None, "reference": "ruler"}
    assert report["parameters"] == {
        "period": None,
        "min_quality": 0.25,
        "flip": False,
        "crop": True,
        "debug": True,
        "export": export_params,
        "minutiae": False,
        "roi": None,
        "finger_position": 0,
        "source_agency": None,
        "options": {"channel": "green", "specular_mask": False, "upright": False},
    }
    assert {o["role"] for o in report["outputs"]} == {"print", "debug", "export", "export-gray"}
    assert len(report["outputs"]) == 7
    assert "identif" in report["disclaimer"]
    expected = extract_fingerprint(load_image(src))
    assert report["measurements"]["ridge_period_px"] == expected.period
    stored = tmp_path / "print.png"
    stored.write_bytes(print_png)
    assert np.array_equal(load_image(stored)[:, :, 0], expected.image)  # same pixels as a direct run


def test_failed_job_is_logged(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in", "noise_only"))
        with pytest.raises(ExtractionError):
            run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert case.entries[-1]["action"] == "job.end"
        assert case.entries[-1]["result"] == "failed"


# ---------------------------------------------------------------- verification


@pytest.fixture
def worked_case(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> Path:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        run_extraction_job(case, evidence.sha256, signer, JobParams())
    return case_dir


def verify(case_dir: Path, keystore: MemoryKeyStore) -> list[str]:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return verify_case(case, case_dir.parent).problems


def test_clean_case_verifies(worked_case: Path, keystore: MemoryKeyStore) -> None:
    assert verify(worked_case, keystore) == []


def test_stripped_signed_head_is_detected(worked_case: Path, keystore: MemoryKeyStore) -> None:
    path = worked_case / "custody.jsonl.enc"
    lines = path.read_bytes().splitlines(keepends=True)
    path.write_bytes(b"".join(lines[:-1]))  # drop the final chain.sign entry of the job
    problems = verify(worked_case, keystore)
    assert any("not covered by a signed custody head" in p for p in problems)


@pytest.mark.parametrize("target", ["artefact", "report", "signature", "stray"])
def test_verify_reports_tampering(worked_case: Path, keystore: MemoryKeyStore, target: str) -> None:
    if target == "artefact":
        path = next((worked_case / "artefacts").iterdir())
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(bytes(data))
    elif target in ("report", "signature"):
        suffix = ".enc" if target == "report" else ".sig"
        path = next(p for p in (worked_case / "reports").iterdir() if p.name.endswith(suffix))
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(bytes(data))
    else:
        (worked_case / "artefacts" / "planted.enc").write_bytes(b"x")
    problems = verify(worked_case, keystore)
    assert problems, target


# ---------------------------------------------------------------- disposal


def dispose(case_dir: Path, keystore: MemoryKeyStore, **kwargs: Any) -> Path:
    args: dict[str, Any] = {"confirm_case_id": case_dir.name, "reason": "proceedings-closed", "actor_key_id": "k" * 16}
    args.update(kwargs)
    return dispose_case(case_dir, PASSPHRASE, keystore, **args)


def test_disposal_rules_and_crypto_erase(worked_case: Path, keystore: MemoryKeyStore) -> None:
    case_id = worked_case.name
    with pytest.raises(RetentionError, match="confirmation"):
        dispose(worked_case, keystore, confirm_case_id="wrong")
    with pytest.raises(RetentionError, match="reason must be one of"):
        dispose(worked_case, keystore, reason="because a named person asked")
    with open_case(worked_case, PASSPHRASE, keystore) as case:
        case.set_legal_hold(True, "court order (synthetic)")
    with pytest.raises(RetentionError, match="legal hold"):
        dispose(worked_case, keystore)
    with open_case(worked_case, PASSPHRASE, keystore) as case:
        case.set_legal_hold(False, "released")
    with pytest.raises(RetentionError, match="retention period"):
        dispose(worked_case, keystore)
    assert worked_case.is_dir()

    record_path = dispose(worked_case, keystore, before_retention=True)
    assert not worked_case.exists()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["case_id"] == case_id
    assert record["before_retention"] is True
    assert record["examiner_key_id"] == "k" * 16
    text = record_path.read_text(encoding="utf-8")
    assert "KT-2026-0001" not in text
    assert ACTOR not in text  # no OS user name or workstation in the retained record
    assert datetime.fromisoformat(record["disposed_utc"]).tzinfo is not None
    assert datetime.fromisoformat(record["disposed_utc"]) <= datetime.now(UTC)


def test_interrupted_disposal_never_leaves_a_readable_case(
    worked_case: Path, keystore: MemoryKeyStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(path: object) -> None:
        raise OSError("power loss")

    monkeypatch.setattr(shutil, "rmtree", crash)
    with pytest.raises(OSError, match="power loss"):
        dispose(worked_case, keystore, before_retention=True)
    stub = json.loads((worked_case / "case.json").read_text(encoding="utf-8"))
    assert "wrapped_dek" not in json.dumps(stub)  # the key was destroyed before anything else
    with pytest.raises(CaseError, match="interrupted"):
        open_case(worked_case, PASSPHRASE, keystore)
    monkeypatch.undo()
    record_path = dispose(worked_case, keystore)  # finishing needs only the confirmation
    assert not worked_case.exists()
    assert json.loads(record_path.read_text(encoding="utf-8"))["reason"] == "proceedings-closed"
