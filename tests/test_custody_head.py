"""Signed custody heads for out-of-band countersigning (OQ-8, R-5): export, verify, detect truncation."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.custody import LOG_FILE
from ridge.case.custody_head import check_head, export_head
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.processing_record import export_log
from ridge.case.store import open_case
from ridge.errors import IntegrityError, OutputExistsError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_a_head_verifies_and_a_later_record_contains_it(setup: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    case_dir, keystore = setup
    store = case_dir.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    head = tmp_path / "head.json"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        doc = export_head(case, store, signer, head)
        assert case.entries[-2]["action"] == "head.export"
        with pytest.raises(OutputExistsError):
            export_head(case, store, signer, head)
        case.import_evidence(photo_file(tmp_path / "in"))  # the log grows after the head
        export_log(case, store, signer, tmp_path / "record.json")
    checked = check_head(head, record=tmp_path / "record.json", expected_key_id=signer.key_id)
    assert (checked.case_id, checked.seq, checked.key_confirmed) == (case_dir.name, doc["seq"], True)
    assert checked.record_entries is not None
    assert check_head(head).record_entries is None


def test_tampered_heads_are_refused(setup: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    case_dir, keystore = setup
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    head = tmp_path / "head.json"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        export_head(case, case_dir.parent, signer, head)
    original = json.loads(head.read_text(encoding="utf-8"))
    for field, value in (("head", "0" * 64), ("seq", original["seq"] + 1), ("key_id", "f" * 16), ("extra", 1)):
        head.write_text(json.dumps({**original, field: value}), encoding="utf-8")
        with pytest.raises(IntegrityError):
            check_head(head)
    head.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(IntegrityError, match="not 0123"):
        check_head(head, expected_key_id="0123456789abcdef")


def test_a_log_truncated_after_the_head_is_detected(setup: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    case_dir, keystore = setup
    store = case_dir.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    head = tmp_path / "head.json"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        export_head(case, store, signer, head)
    log = case_dir / LOG_FILE
    lines = log.read_bytes().splitlines(keepends=True)
    log.write_bytes(b"".join(lines[:-2]))  # cut the head export off the end: the chain itself stays valid
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        case.import_evidence(photo_file(tmp_path / "in"))  # ... and carry on, as a forger would
        export_log(case, store, signer, tmp_path / "record.json")
    with pytest.raises(IntegrityError, match="not the countersigned head"):
        check_head(head, record=tmp_path / "record.json")


def test_an_older_record_is_named_as_older(setup: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    case_dir, keystore = setup
    store = case_dir.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        export_log(case, store, signer, tmp_path / "record.json")
        export_head(case, store, signer, tmp_path / "head.json")
    with pytest.raises(IntegrityError, match="older than the head"):
        check_head(tmp_path / "head.json", record=tmp_path / "record.json")


def test_cli_and_sidecar_export_and_check_heads(
    setup: tuple[Path, MemoryKeyStore],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case_dir, keystore = setup
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    head = tmp_path / "head.json"
    assert main(["head", str(case_dir), "--to", str(head)]) == 0
    assert main(["log", str(case_dir), "--to", str(tmp_path / "record.json")]) == 0
    capsys.readouterr()
    assert main(["check-head", str(head), "--record", str(tmp_path / "record.json")]) == 0
    shown = capsys.readouterr().out
    assert "contains this head unchanged" in shown
    assert "confirm key" in shown
    session = Session(keystore_factory=lambda: keystore)
    unlock = {"store": str(case_dir.parent), "case_id": case_dir.name, "passphrase": PASSPHRASE}
    message = {"jsonrpc": "2.0", "id": 1, "method": "session.unlock", "params": unlock}
    assert "result" in json.loads(handle(json.dumps(message).encode(), session))
    dest = str((tmp_path / "head2.json").resolve())
    message = {"jsonrpc": "2.0", "id": 2, "method": "head.export", "params": {"dest": dest}}
    exported = json.loads(handle(json.dumps(message).encode(), session))["result"]
    assert check_head(Path(dest), expected_key_id=exported["key_id"]).seq == exported["seq"]
    session.close()
