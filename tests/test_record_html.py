"""Readable copies made offline: only after the file verified, escaped, never over an existing file."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.notes import add_note
from ridge.case.package import RECORD_HTML, check_package, export_package
from ridge.case.processing_record import export_log
from ridge.case.record_html import write_record_html
from ridge.case.report_html import write_exported_report_html
from ridge.case.reports import export_report
from ridge.case.store import open_case
from ridge.errors import IntegrityError, OutputExistsError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path]:
    root = tmp_path_factory.mktemp("offline")
    keystore = MemoryKeyStore()
    store = root / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(new_case(store, keystore), PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(root / "in"))
        job = run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id
        add_note(case, "<script>alert(1)</script> glare\nsecond line", job_id=job)
        export_report(case, store, job, root / "report.json")
        export_log(case, store, signer, root / "record.json")
        export_package(case, store, signer, root / "package")
    return root / "report.json", root / "record.json", root / "package"


def test_a_verified_record_becomes_a_readable_page(exported: tuple[Path, Path, Path], tmp_path: Path) -> None:
    _, record, _ = exported
    check = write_record_html(record, tmp_path / "record.html")
    page = (tmp_path / "record.html").read_text(encoding="utf-8")
    assert f"{check.entries}, {check.signed_heads} signed head(s), chain verified" in page
    assert "examiner.note" in page
    assert "&lt;script&gt;" in page
    assert "<script" not in page
    assert "glare<br>second line" in page
    with pytest.raises(OutputExistsError):
        write_record_html(record, tmp_path / "record.html")


def test_nothing_is_written_for_a_file_that_does_not_verify(exported: tuple[Path, Path, Path], tmp_path: Path) -> None:
    report, record, _ = exported
    doc = json.loads(record.read_bytes())
    doc["entries"][1]["action"] = "edited"
    (tmp_path / "bad-record.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(IntegrityError):
        write_record_html(tmp_path / "bad-record.json", tmp_path / "bad-record.html")
    assert not (tmp_path / "bad-record.html").exists()
    (tmp_path / "bad.json").write_bytes(report.read_bytes().replace(b'"flip":false', b'"flip":true'))
    (tmp_path / "bad.json.sig").write_bytes(report.with_name(report.name + ".sig").read_bytes())
    with pytest.raises(IntegrityError):
        write_exported_report_html(tmp_path / "bad.json", tmp_path / "bad.html")
    assert not (tmp_path / "bad.html").exists()


def test_cli_and_package(
    exported: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report, record, package = exported
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", MemoryKeyStore)
    assert main(["check-report", str(report), "--html", str(tmp_path / "r.html")]) == 0
    assert main(["check-log", str(record), "--html", str(tmp_path / "l.html")]) == 0
    assert capsys.readouterr().out.count("readable copy written") == 2
    assert "not signed" in (tmp_path / "r.html").read_text(encoding="utf-8")
    assert (package / RECORD_HTML).is_file()
    check_package(package)  # the readable record is listed in the signed manifest
