"""Checking exported files without a store: every kind goes to its verifier; the signer is named."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ridge.case.cli import main
from ridge.case.custody_head import export_head
from ridge.case.file_check import check_exported
from ridge.case.identity import create_identity, public_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.key_card import write_card
from ridge.case.key_register import SCHEMA as REGISTER_SCHEMA
from ridge.case.keys import b64
from ridge.case.limits import FILE
from ridge.case.limits import SCHEMA as LIMITS_SCHEMA
from ridge.case.package import export_package
from ridge.case.processing_record import export_log
from ridge.case.reports import export_report
from ridge.case.store import open_case
from ridge.errors import IntegrityError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture(scope="module")
def files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("files")
    keystore = MemoryKeyStore()
    store = root / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(new_case(store, keystore), PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(root / "in"))
        job = run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id
        export_report(case, store, job, root / "report.json")
        export_log(case, store, signer, root / "record.json")
        export_head(case, store, signer, root / "head.json")
        export_package(case, store, signer, root / "package")
    write_card(signer, "examiner", "Examiner A", root / "card.json")
    key_id, public = public_identity(store)
    entry = {"key_id": key_id, "public_key": b64(public), "holder": "Examiner A", "role": "examiner"}
    (root / "register.json").write_text(
        json.dumps({"schema": REGISTER_SCHEMA, "laboratory": "Synthetic Lab", "keys": [entry]}), encoding="utf-8"
    )
    (root / FILE).write_text(json.dumps({"schema": LIMITS_SCHEMA, "source": "VR-1"}), encoding="utf-8")
    return {
        "report": root / "report.json",
        "record": root / "record.json",
        "head": root / "head.json",
        "package": root / "package",
        "card": root / "card.json",
        "register": root / "register.json",
        "limits": root / FILE,
    }


@pytest.mark.parametrize("kind", ["report", "record", "head", "package", "card", "register", "limits"])
def test_every_kind_is_verified(files: dict[str, Path], kind: str) -> None:
    result = check_exported(files[kind])
    assert result.kind == kind
    assert result.details


@pytest.mark.parametrize("kind", ["report", "record", "head", "package"])
def test_a_register_names_the_signer(files: dict[str, Path], kind: str) -> None:
    result = check_exported(files[kind], files["register"])
    assert result.holder == "Examiner A"
    assert any("registered to Examiner A" in line for line in result.details)


def test_tampered_and_unknown_files_are_refused(files: dict[str, Path], tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_bytes(files["report"].read_bytes().replace(b'"flip":false', b'"flip":true'))
    (tmp_path / "bad.json.sig").write_bytes(files["report"].with_name("report.json.sig").read_bytes())
    with pytest.raises(IntegrityError):
        check_exported(tmp_path / "bad.json")
    for name, data in (("x.txt", b"not json"), ("y.json", b"[1]"), ("z.json", b'{"schema": "other/1"}')):
        (tmp_path / name).write_bytes(data)
        with pytest.raises(ParameterError):
            check_exported(tmp_path / name)


def test_sidecar(files: dict[str, Path]) -> None:
    session = Session(keystore_factory=MemoryKeyStore)

    def rpc(params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": "files.check", "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    reply = rpc({"path": str(files["package"].resolve()), "register": str(files["register"].resolve())})
    assert (reply["result"]["kind"], reply["result"]["holder"]) == ("package", "Examiner A")
    assert "error" in rpc({"path": "relative/path.json"})


def test_cli(files: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(files["record"]), "--register", str(files["register"])]) == 0
    shown = capsys.readouterr().out
    assert "Processing record: verified" in shown
    assert "registered to Examiner A" in shown
    assert main(["check", str(files["card"])]) == 0


def test_a_card_is_checked_against_a_register(files: dict[str, Path], tmp_path: Path) -> None:
    result = check_exported(files["card"], files["register"])
    assert result.holder == "Examiner A"
    doc = json.loads(files["register"].read_bytes())
    doc["keys"][0]["holder"] = "Someone Else"
    (tmp_path / "other.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(IntegrityError, match="the register lists"):
        check_exported(files["card"], tmp_path / "other.json")
    doc["keys"][0]["revoked"] = "2000-01-01"
    doc["keys"][0]["holder"] = "Examiner A"
    (tmp_path / "revoked.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(IntegrityError, match="revoked"):
        check_exported(files["card"], tmp_path / "revoked.json")
