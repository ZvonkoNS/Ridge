"""Disclosure packages: signed records in a new folder, verified offline, tampering detected."""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import rfc8785

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.package import MANIFEST, RECORD, check_package, export_package
from ridge.case.store import open_case
from ridge.errors import IntegrityError, OutputExistsError
from ridge.image_io import publish
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture(scope="module")
def package(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, MemoryKeyStore, Path]:
    root = tmp_path_factory.mktemp("pkg")
    keystore = MemoryKeyStore()
    store = root / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    case_dir = new_case(store, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(root / "in"))
        run_extraction_job(case, evidence.sha256, signer, JobParams())
        run_extraction_job(case, evidence.sha256, signer, JobParams(flip=True))
        export_package(case, store, signer, root / "package")
    return root / "package", signer.key_id, keystore, case_dir


@pytest.fixture
def copy(package: tuple[Path, str, MemoryKeyStore, Path], tmp_path: Path) -> Path:
    return Path(shutil.copytree(package[0], tmp_path / "copy"))


def test_a_package_holds_the_signed_records_and_no_images(package: tuple[Path, str, MemoryKeyStore, Path]) -> None:
    folder, key_id, keystore, case_dir = package
    names = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert len([n for n in names if n.startswith("reports/") and n.endswith(".json")]) == 2
    assert RECORD in names
    assert MANIFEST in names
    assert not [n for n in names if n.endswith((".png", ".jpg", ".tif"))]
    check = check_package(folder, expected_key_id=key_id)
    assert (check.reports, check.key_confirmed) == (2, True)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        exported = [e for e in case.entries if e["action"] == "package.export"]
    assert exported[-1]["package_id"] == check.package_id  # the export is in the custody log


def test_an_existing_folder_is_never_written_into(package: tuple[Path, str, MemoryKeyStore, Path]) -> None:
    folder, _, keystore, case_dir = package
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    before = sorted(folder.rglob("*"))
    with open_case(case_dir, PASSPHRASE, keystore) as case, pytest.raises(OutputExistsError):
        export_package(case, case_dir.parent, signer, folder)
    assert sorted(folder.rglob("*")) == before


def _rewrite_report(folder: Path) -> None:
    report = next((folder / "reports").glob("*.json"))
    doc = json.loads(report.read_bytes())
    doc["parameters"]["flip"] = not doc["parameters"]["flip"]
    report.write_bytes(bytes(rfc8785.dumps(doc)))


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (_rewrite_report, "changed after signing"),
        (lambda f: (f / "reports" / "extra.txt").write_text("x", encoding="utf-8"), "files added"),
        (lambda f: next((f / "reports").glob("*.sig")).unlink(), "removed"),
        (lambda f: (f / MANIFEST).write_bytes((f / MANIFEST).read_bytes() + b" "), "canonical"),
        (lambda f: (f / (MANIFEST + ".sig")).write_bytes(base64.b64encode(b"\0" * 64)), "does not verify"),
    ],
)
def test_tampering_is_detected(copy: Path, tamper: object, message: str) -> None:
    tamper(copy)  # type: ignore[operator]
    with pytest.raises(IntegrityError, match=message):
        check_package(copy)


def test_a_resigned_manifest_still_needs_the_logged_reports(
    copy: Path, package: tuple[Path, str, MemoryKeyStore, Path]
) -> None:
    """Even the examiner key cannot swap a report: the custody log names the signed report hashes."""
    _, _, keystore, case_dir = package
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    reports = sorted((copy / "reports").glob("*.json"))
    reports[0].write_bytes(reports[1].read_bytes())  # a valid, signed report of the other job
    reports[0].with_name(reports[0].name + ".sig").write_bytes(
        reports[1].with_name(reports[1].name + ".sig").read_bytes()
    )
    manifest = json.loads((copy / MANIFEST).read_bytes())
    for entry in manifest["files"]:
        data = (copy / entry["path"]).read_bytes()
        entry["size"] = len(data)
        entry["sha256"] = hashlib.sha256(data).hexdigest()
    canonical = bytes(rfc8785.dumps(manifest))
    (copy / MANIFEST).write_bytes(canonical)
    (copy / (MANIFEST + ".sig")).write_bytes(base64.b64encode(signer.sign(canonical)))
    with pytest.raises(IntegrityError, match="another job"):
        check_package(copy)


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    keystore = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(store, keystore)
    assert main(["package", str(case_dir), "--to", str(tmp_path / "out")]) == 0
    assert "0 report(s)" in capsys.readouterr().out
    assert main(["check-package", str(tmp_path / "out")]) == 0
    assert "confirm key" in capsys.readouterr().out
    assert main(["check-package", str(tmp_path / "out"), "--key-id", "0123456789abcdef"]) == 1
    assert main(["package", str(case_dir), "--to", str(tmp_path / "out")]) == 1  # never into an existing folder
    session = Session(keystore_factory=lambda: keystore)
    unlock = {"store": str(store.resolve()), "case_id": case_dir.name, "passphrase": PASSPHRASE}
    for method, params in (("session.unlock", unlock), ("package.export", {"dest": str((tmp_path / "gui").resolve())})):
        reply = json.loads(
            handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), session)
        )
    assert reply["result"]["reports"] == 0
    assert check_package(tmp_path / "gui").package_id == reply["result"]["package_id"]
    session.close()


def test_a_failure_while_signing_the_manifest_is_logged(
    package: tuple[Path, str, MemoryKeyStore, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, keystore, case_dir = package
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)

    def full_disk(path: Path, data: bytes, **kwargs: object) -> None:
        if path.name == MANIFEST:
            raise OSError(28, "No space left on device")
        publish(path, data, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("ridge.case.package.publish", full_disk)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        with pytest.raises(OSError, match="No space left"):
            export_package(case, case_dir.parent, signer, tmp_path / "partial")
        assert (case.entries[-1]["action"], case.entries[-1]["result"]) == ("package.export", "failed")
    with pytest.raises(IntegrityError):
        check_package(tmp_path / "partial")  # no signed manifest: never a valid package
