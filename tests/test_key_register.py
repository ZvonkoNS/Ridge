"""The laboratory key register: strict parsing, role and validity checks, and the --register option."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, key_id_for, public_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.key_register import SCHEMA, confirm_key, parse_register
from ridge.case.keys import b64
from ridge.case.limits import FILE
from ridge.case.limits import SCHEMA as LIMITS_SCHEMA
from ridge.case.limits_signing import create_fqm_key, sign_limits
from ridge.case.store import open_case
from ridge.errors import IntegrityError, ParameterError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file

PUBLIC = bytes(range(32))
KEY_ID = key_id_for(PUBLIC)


def entry(**fields: Any) -> dict[str, Any]:
    return {"key_id": KEY_ID, "public_key": b64(PUBLIC), "holder": "Examiner A", "role": "examiner", **fields}


def register(*keys: dict[str, Any]) -> bytes:
    return json.dumps({"schema": SCHEMA, "laboratory": "Synthetic Lab", "keys": list(keys)}).encode()


def test_a_register_names_holders_roles_and_validity() -> None:
    reg = parse_register(register(entry(valid_from="2026-01-01", valid_until="2026-12-31", revoked="2026-11-01")))
    key = confirm_key(reg, KEY_ID, "examiner", "2026-10-18T08:00:00Z")
    assert (key.holder, reg.laboratory) == ("Examiner A", "Synthetic Lab")
    for when, problem in [
        ("2025-12-31T23:59:59Z", "not valid"),
        ("2026-11-01T00:00:00Z", "revoked"),
        ("2027-01-01T00:00:00Z", "not valid"),
        ("yesterday", "not a date"),
    ]:
        with pytest.raises(IntegrityError, match=problem):
            confirm_key(reg, KEY_ID, "examiner", when)
    with pytest.raises(IntegrityError, match="not for the fqm role"):
        confirm_key(reg, KEY_ID, "fqm", "2026-10-18T08:00:00Z")
    with pytest.raises(IntegrityError, match="not in the Synthetic Lab key register"):
        confirm_key(reg, "0" * 16, "examiner", "2026-10-18T08:00:00Z")


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        json.dumps({"schema": "other", "laboratory": "L", "keys": [entry()]}).encode(),
        json.dumps({"schema": SCHEMA, "laboratory": "L", "keys": [], "extra": 1}).encode(),
        register(),
        register(entry(key_id="0" * 16)),
        register(entry(public_key="not base64!")),
        register(entry(role="admin")),
        register(entry(extra=True)),
        register(entry(valid_from="18.10.2026")),
        register(entry(valid_from="2027-01-01", valid_until="2026-01-01")),
        register(entry(holder="Examiner\u202eA")),
        register(entry(), entry()),
    ],
)
def test_malformed_registers_are_refused(data: bytes) -> None:
    with pytest.raises(ParameterError):
        parse_register(data)


@pytest.fixture
def signed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    keystore = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(cli_common, "KDF_PARAMS", FAST_KDF)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    case_dir = new_case(store, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        job = run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id
    assert main(["report", str(case_dir), job, "--to", str(tmp_path / "report.json")]) == 0
    key_id, public = public_identity(store)
    lab = register(entry(key_id=key_id, public_key=b64(public), holder="Examiner B"))
    (tmp_path / "register.json").write_bytes(lab)
    return case_dir, tmp_path / "register.json", key_id


def test_checks_name_the_registered_holder(
    signed: tuple[Path, Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_dir, reg, key_id = signed
    capsys.readouterr()
    assert main(["check-report", str(tmp_path / "report.json"), "--register", str(reg)]) == 0
    assert f"key {key_id} registered to Examiner B (examiner key" in capsys.readouterr().out
    assert main(["package", str(case_dir), "--to", str(tmp_path / "pkg")]) == 0
    assert main(["check-package", str(tmp_path / "pkg"), "--register", str(reg)]) == 0
    assert main(["check-log", str(tmp_path / "pkg" / "processing-record.json"), "--register", str(reg)]) == 0
    assert "registered to Examiner B" in capsys.readouterr().out
    assert main(["register", "--check", str(reg)]) == 0
    assert "Synthetic Lab key register, 1 key(s)" in capsys.readouterr().out


def test_an_unregistered_or_revoked_key_fails_the_check(signed: tuple[Path, Path, str], tmp_path: Path) -> None:
    _, reg, _ = signed
    doc = json.loads(reg.read_bytes())
    doc["keys"][0]["revoked"] = "2000-01-01"
    reg.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["check-report", str(tmp_path / "report.json"), "--register", str(reg)]) == 1
    reg.write_bytes(register(entry()))  # another key only
    assert main(["check-report", str(tmp_path / "report.json"), "--register", str(reg)]) == 1


def test_signed_limits_need_a_registered_fqm_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fqm = create_fqm_key(tmp_path / "fqm.json", "quality manager's own long passphrase", FAST_KDF)
    limits = tmp_path / FILE
    limits.write_text(json.dumps({"schema": LIMITS_SCHEMA, "source": "VR-1"}), encoding="utf-8")
    sign_limits(limits, tmp_path / "fqm.json", "quality manager's own long passphrase")
    as_fqm = entry(key_id=fqm.key_id, public_key=b64(fqm.public_key), holder="FQM C", role="fqm")
    (tmp_path / "reg.json").write_bytes(register(as_fqm))
    assert main(["limits", "--check", str(limits), "--register", str(tmp_path / "reg.json")]) == 0
    assert "registered to FQM C (fqm key" in capsys.readouterr().out
    (tmp_path / "reg.json").write_bytes(register({**as_fqm, "role": "examiner"}))
    assert main(["limits", "--check", str(limits), "--register", str(tmp_path / "reg.json")]) == 1
