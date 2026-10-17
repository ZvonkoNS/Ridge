"""Processing-record export (PRD PRIV-3): signed, readable, verifiable offline; tampering detected."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ridge.case.crypto import sha256_hex
from ridge.case.custody import canonical
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.processing_record import SCHEMA, check_exported_log, export_log
from ridge.case.store import open_case
from ridge.errors import InputRejectedError, IntegrityError, OutputExistsError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(store, keystore)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        run_extraction_job(case, evidence.sha256, signer, JobParams())
    return case_dir


def export(case_dir: Path, keystore: MemoryKeyStore, dest: Path, *, overwrite: bool = False) -> int:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return export_log(case, case_dir.parent, signer, dest, overwrite=overwrite)


@pytest.fixture
def record(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> Path:
    dest = tmp_path / "record.json"
    export(case_dir, keystore, dest)
    return dest


def test_export_is_signed_complete_and_readable(record: Path, case_dir: Path) -> None:
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["schema"] == SCHEMA
    assert data["case_id"] == case_dir.name
    actions = [e["action"] for e in data["entries"]]
    assert actions[0] == "case.create"
    assert actions[-2:] == ["log.export", "chain.sign"]
    check = check_exported_log(record)
    assert (check.entries, check.key_confirmed) == (len(actions), False)
    assert data["entries"][-2]["case_id"] == case_dir.name  # the case id is inside the signed chain
    assert check.signed_heads == 2  # after the job and after the export
    assert check_exported_log(record, expected_key_id=check.key_id.upper()).key_confirmed is True
    with pytest.raises(IntegrityError, match="not the expected key"):
        check_exported_log(record, expected_key_id="0" * 16)


def test_export_refuses_to_overwrite(record: Path, case_dir: Path, keystore: MemoryKeyStore) -> None:
    with pytest.raises(OutputExistsError):
        export(case_dir, keystore, record)
    count = export(case_dir, keystore, record, overwrite=True)
    assert len(json.loads(record.read_text(encoding="utf-8"))["entries"]) == count


def test_export_needs_the_store_identity(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    other_store = tmp_path / "other"
    stranger = create_identity(other_store, PASSPHRASE, keystore, FAST_KDF)
    with open_case(case_dir, PASSPHRASE, keystore) as case, pytest.raises(IntegrityError, match="not this store"):
        export_log(case, case_dir.parent, stranger, tmp_path / "x.json")


def test_failed_write_is_logged(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ridge.case import processing_record  # noqa: PLC0415

    def refuse(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(processing_record, "publish", refuse)
    with pytest.raises(PermissionError):
        export(case_dir, keystore, tmp_path / "x.json")
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert case.entries[-1]["action"] == "log.export"
        assert case.entries[-1]["result"] == "failed"


def rewrite(record: Path, change: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(record.read_text(encoding="utf-8"))
    change(data)
    record.write_text(json.dumps(data), encoding="utf-8")


def relink(entries: list[dict[str, Any]]) -> None:
    """Recompute every prev link, as a forger who knows the format would."""
    head = "0" * 64
    for entry in entries:
        entry["prev"] = head
        head = sha256_hex(canonical(entry))


def test_edited_entries_are_detected(record: Path) -> None:
    rewrite(record, lambda d: d["entries"][1].update(actor="someone-else"))
    with pytest.raises(IntegrityError, match="entry 2: does not link"):
        check_exported_log(record)


def test_relinked_forgery_fails_the_signature(record: Path) -> None:
    def forge(d: dict[str, Any]) -> None:
        d["entries"][1]["actor"] = "someone-else"
        relink(d["entries"])

    rewrite(record, forge)
    with pytest.raises(IntegrityError, match="signed head"):
        check_exported_log(record)


def test_removed_entries_are_detected(record: Path) -> None:
    rewrite(record, lambda d: d["entries"].pop(2))
    with pytest.raises(IntegrityError, match="sequence number"):
        check_exported_log(record)


def test_appended_entries_are_refused(record: Path) -> None:
    def append(d: dict[str, Any]) -> None:
        last = d["entries"][-1]
        d["entries"].append({**last, "seq": last["seq"] + 1, "action": "evidence.read", "prev": ""})
        d["entries"][-1].pop("signature")
        relink(d["entries"])  # the earlier links are unchanged; only the new entry is linked

    rewrite(record, append)
    with pytest.raises(IntegrityError, match="does not end with a signed"):
        check_exported_log(record)


def test_stripped_signatures_are_refused(record: Path) -> None:
    def strip(d: dict[str, Any]) -> None:
        d["entries"] = [e for e in d["entries"] if e["action"] != "chain.sign"]
        for seq, entry in enumerate(d["entries"]):
            entry["seq"] = seq
        relink(d["entries"])

    rewrite(record, strip)
    with pytest.raises(IntegrityError, match="does not end with a signed"):
        check_exported_log(record)


def test_case_id_is_authenticated(record: Path) -> None:
    rewrite(record, lambda d: d.update(case_id="00000000-0000-0000-0000-000000000000"))
    with pytest.raises(IntegrityError, match="case id"):
        check_exported_log(record)


MALFORMED: dict[str, tuple[Callable[[dict[str, Any]], None], str]] = {
    "schema": (lambda d: d.update(schema="x/1"), "not a ridge.processing-record/1 file"),
    "identity": (lambda d: d.update(identity=None), "names no identity"),
    "public key": (lambda d: d["identity"].update(public_key="@@"), "public key is not base64"),
    "key id": (lambda d: d["identity"].update(key_id="0" * 16), "does not match its public key"),
    "entries": (lambda d: d.update(entries=[]), "no custody entries"),
    "signature": (lambda d: d["entries"][-1].update(signature="@@"), "malformed"),
}


@pytest.mark.parametrize("kind", MALFORMED)
def test_malformed_records(record: Path, kind: str) -> None:
    change, message = MALFORMED[kind]
    rewrite(record, change)
    with pytest.raises(IntegrityError, match=message):
        check_exported_log(record)


def test_non_json_and_oversized_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ridge.case import processing_record  # noqa: PLC0415

    path = tmp_path / "r.json"
    for text in ("not json", '{"schema": NaN}'):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(IntegrityError, match="UTF-8 JSON"):
            check_exported_log(path)
    monkeypatch.setattr(processing_record, "MAX_RECORD_BYTES", 4)
    with pytest.raises(InputRejectedError):
        check_exported_log(path)
