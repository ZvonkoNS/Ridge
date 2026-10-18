"""Limits of use signed by the Forensic Quality Manager: key file, signature, verification on every job."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.keys import b64
from ridge.case.limits import FILE, SCHEMA, SIGNATURE_FILE, load_limits, read_limits, render_lines, report_section
from ridge.case.limits_signing import create_fqm_key, sign_limits, unlock_fqm_key
from ridge.case.store import open_case
from ridge.errors import IntegrityError, KeyCustodyError, OutputExistsError, ParameterError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file

FQM_PASSPHRASE = "quality manager's own long passphrase"  # noqa: S105  # synthetic test passphrase


def write_limits(path: Path, **fields: object) -> bytes:
    data = json.dumps({"schema": SCHEMA, "source": "VR-2027-01", **fields}).encode()
    path.write_bytes(data)
    return data


@pytest.fixture
def signed_store(tmp_path: Path) -> tuple[Path, str]:
    store = tmp_path / "store"
    store.mkdir()
    key = create_fqm_key(tmp_path / "fqm-key.json", FQM_PASSPHRASE, FAST_KDF)
    write_limits(store / FILE, min_ridge_period_px=2)
    sign_limits(store / FILE, tmp_path / "fqm-key.json", FQM_PASSPHRASE)
    return store, key.key_id


def test_a_signed_file_names_its_key(signed_store: tuple[Path, str]) -> None:
    store, key_id = signed_store
    limits = load_limits(store)
    assert limits is not None
    assert limits.signed_by is not None
    assert limits.signed_by["key_id"] == key_id
    section = report_section(limits, {"measurements": {"ridge_period_px": 9.0}})
    assert section["signed_by"] == limits.signed_by
    assert f"signed with key {key_id}" in "\n".join(render_lines(section))


def test_any_change_or_removal_stops_jobs(signed_store: tuple[Path, str]) -> None:
    store, _ = signed_store
    write_limits(store / FILE, min_ridge_period_px=1)  # loosened after signing
    with pytest.raises(ParameterError, match="does not verify"):
        load_limits(store)
    (store / FILE).unlink()
    with pytest.raises(ParameterError, match="is missing"):
        load_limits(store)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: {**d, "key_id": "0" * 16},
        lambda d: {**d, "limits_sha256": "0" * 64},
        lambda d: {**d, "signature": b64(b"\0" * 64)},
        lambda d: {**d, "public_key": b64(b"\1" * 32)},
        lambda d: {**d, "extra": 1},
        lambda d: {**d, "schema": "ridge.limits-signature/2"},
        lambda d: "not an object",
    ],
)
def test_a_tampered_signature_is_refused(signed_store: tuple[Path, str], change: object) -> None:
    store, _ = signed_store
    doc = json.loads((store / SIGNATURE_FILE).read_text(encoding="utf-8"))
    (store / SIGNATURE_FILE).write_text(json.dumps(change(doc)), encoding="utf-8")  # type: ignore[operator]
    with pytest.raises(ParameterError, match="does not verify"):
        load_limits(store)


def test_key_files_are_sealed_and_never_replaced(tmp_path: Path) -> None:
    key = create_fqm_key(tmp_path / "k.json", FQM_PASSPHRASE, FAST_KDF)
    assert "sealed_private_key" in (tmp_path / "k.json").read_text(encoding="utf-8")
    assert unlock_fqm_key(tmp_path / "k.json", FQM_PASSPHRASE).key_id == key.key_id
    with pytest.raises(KeyCustodyError):
        unlock_fqm_key(tmp_path / "k.json", "not the right passphrase at all")
    with pytest.raises(OutputExistsError):
        create_fqm_key(tmp_path / "k.json", FQM_PASSPHRASE, FAST_KDF)
    (tmp_path / "junk.json").write_text("{}", encoding="utf-8")
    with pytest.raises(IntegrityError):
        unlock_fqm_key(tmp_path / "junk.json", FQM_PASSPHRASE)
    write_limits(tmp_path / "bad.json", unknown=1)
    with pytest.raises(ParameterError):
        sign_limits(tmp_path / "bad.json", tmp_path / "k.json", FQM_PASSPHRASE)  # an invalid file is never signed
    assert not (tmp_path / "bad.json.sig").exists()


def test_jobs_record_the_signer(signed_store: tuple[Path, str], tmp_path: Path) -> None:
    store, key_id = signed_store
    keystore = MemoryKeyStore()
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(new_case(store, keystore), PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
    assert outcome.report["limits_of_use"]["signed_by"]["key_id"] == key_id


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli_common, "KDF_PARAMS", FAST_KDF)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": FQM_PASSPHRASE)
    key = tmp_path / "fqm-key.json"
    assert main(["fqm-key", "--to", str(key)]) == 0
    key_id = capsys.readouterr().out.split("FQM key ")[1].split()[0]
    limits = tmp_path / "limits-of-use.json"
    write_limits(limits, require_ruler=True)
    assert main(["limits", "--check", str(limits)]) == 0
    assert "not signed" in capsys.readouterr().out
    assert main(["limits", "--sign", str(limits)]) == 1  # --key is required
    assert main(["limits", "--sign", str(limits), "--key", str(key)]) == 0
    assert main(["limits", "--sign", str(limits), "--key", str(key)]) == 1  # FILE.sig exists
    assert main(["limits", "--sign", str(limits), "--key", str(key), "--overwrite"]) == 0
    capsys.readouterr()
    assert main(["limits", "--check", str(limits), "--key-id", key_id]) == 0
    assert f"signed with key {key_id}" in capsys.readouterr().out
    assert main(["limits", "--check", str(limits), "--key-id", "0123456789abcdef"]) == 1
    assert read_limits(limits).signed_by is not None
