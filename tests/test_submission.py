"""Submission record and AFIS cover sheet (PRD FR-38): examiner statements recorded, never inferred."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.cover_sheet import export_cover_sheet, render_cover_sheet
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.report_html import render_report_html
from ridge.case.reports import load_report, render_report
from ridge.case.reproduce import params_from_report
from ridge.case.store import open_case
from ridge.case.submission import (
    FINGER_POSITIONS,
    IMPRESSION,
    Submission,
    capture_device,
    check_finger_position,
    check_source_agency,
    submission_line,
    submission_record,
)
from ridge.errors import OutputExistsError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests import metadata_samples as samples
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_finger_codes_and_agency_text_are_validated() -> None:
    assert len(FINGER_POSITIONS) == 11
    assert FINGER_POSITIONS[0] == "unknown"
    assert FINGER_POSITIONS[2] == "right index"
    assert FINGER_POSITIONS[10] == "left little"
    assert check_finger_position(7) == 7
    for bad in (-1, 11, 1.0, "2", True, None):
        with pytest.raises(ParameterError):
            check_finger_position(bad)
    assert check_source_agency("  Police of Synthetica  ") == "Police of Synthetica"
    assert check_source_agency(None) is None
    for bad_text in ("", "a\x07b", "x" * 201, 5):
        with pytest.raises(ParameterError):
            check_source_agency(bad_text)
    with pytest.raises(ParameterError):
        Submission(finger_position=12)
    with pytest.raises(ParameterError):
        JobParams(finger_position=3, source_agency="").submission()


def test_the_record_names_the_statements_and_the_unverified_camera() -> None:
    metadata = {"summary": [{"name": "Camera", "id": "EXIF Make, Model", "value": "Synthetic Camera Co Model 7"}]}
    record = submission_record(Submission(2, "Police of Synthetica"), metadata)
    assert record["finger_position"] == 2
    assert record["finger"] == "right index"
    assert record["source_agency"] == "Police of Synthetica"
    assert record["impression"] == IMPRESSION
    assert record["capture_device"] == "Synthetic Camera Co Model 7"
    assert "not verified" in record["capture_device_note"]
    assert "identification" in record["notice"]
    assert capture_device(None) is None
    assert capture_device({"summary": [{"name": "Lens", "value": "x"}]}) is None
    plain = submission_record(Submission(), None)
    assert (plain["finger"], plain["source_agency"], plain["capture_device"]) == ("unknown", None, None)
    assert "names no camera" in plain["capture_device_note"]
    assert submission_line(record).startswith(
        "Submission    finger position 2 (right index), source agency Police of Synthetica"
    )
    assert "not stated" in submission_line(plain)
    assert submission_line(None) == ""


def test_jobs_record_the_submission_and_reports_render_it(
    case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path
) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    photo = tmp_path / "in" / "camera.jpg"
    photo.parent.mkdir()
    photo.write_bytes(samples.full_jpeg())
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        params = JobParams(finger_position=7, source_agency="Police of Synthetica")
        try:
            outcome = run_extraction_job(case, evidence.sha256, signer, params)
        except Exception:  # noqa: BLE001  # the tiny camera JPEG may hold no ridge pattern: use the synthetic finger
            evidence = case.import_evidence(photo_file(tmp_path / "in2"))
            outcome = run_extraction_job(case, evidence.sha256, signer, params)
        section = outcome.report["submission"]
        assert (section["finger_position"], section["finger"]) == (7, "left index")
        assert section["source_agency"] == "Police of Synthetica"
        assert outcome.report["parameters"]["finger_position"] == 7
        assert outcome.report["parameters"]["source_agency"] == "Police of Synthetica"
        signed = load_report(case, store, outcome.job_id)
        text = render_report(signed.report, signer.key_id)
        assert "Submission    finger position 7 (left index), source agency Police of Synthetica" in text
        assert "finger position 7 (left index)" in render_report_html(signed)
        assert params_from_report(outcome.report["parameters"]) == params
        older = dict(outcome.report["parameters"])
        del older["finger_position"], older["source_agency"]
        rebuilt = params_from_report(older)
        assert (rebuilt.finger_position, rebuilt.source_agency) == (0, None)
        with pytest.raises(ParameterError):
            run_extraction_job(case, evidence.sha256, signer, JobParams(finger_position=42))


def test_capture_device_comes_from_the_photo_file(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    photo = tmp_path / "in" / "finger_gps.png"
    photo.parent.mkdir()
    photo.write_bytes(samples.finger_png_with_gps())
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
        section = outcome.report["submission"]
        expected = capture_device(outcome.report["input"]["metadata"])
        assert section["capture_device"] == expected
        assert section["finger"] == "unknown"


def test_cover_sheet_lists_the_files_to_attach_and_is_logged(
    case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path
) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        outcome = run_extraction_job(
            case, evidence.sha256, signer, JobParams(finger_position=2, source_agency="Police of Synthetica")
        )
        signed = load_report(case, store, outcome.job_id)
        page = render_cover_sheet(signed)
        gray = next(o for o in outcome.outputs if o.role == "export-gray")
        binary = next(o for o in outcome.outputs if o.role == "export")
        assert gray.sha256 in page
        assert binary.sha256 in page
        assert gray.label in page
        assert "Grayscale comparison export (recommended for AFIS)" in page
        assert "2: right index" in page
        assert "Police of Synthetica" in page
        assert "not an identification" in page.lower() or "does not identify" in page
        assert "Scale notice" in page  # no ruler: the notice travels with the submission
        assert "<script" not in page
        assert "default-src 'none'" in page
        assert "not signed" in page
        dest = tmp_path / "cover.html"
        export_cover_sheet(case, store, outcome.job_id, dest)
        entry = case.entries[-1]
        assert (entry["action"], entry["job_id"]) == ("cover.export", outcome.job_id)
        assert dest.read_text(encoding="utf-8") == page
        with pytest.raises(OutputExistsError):
            export_cover_sheet(case, store, outcome.job_id, dest)
        older = dict(signed.report)
        del older["submission"]
        from ridge.case.reports import SignedReport  # noqa: PLC0415

        rendered = render_cover_sheet(
            SignedReport(signed.job_id, signed.canonical, signed.signature, signed.key_id, older)
        )
        assert "report made before submission records" in rendered


def test_cli_and_sidecar_write_the_cover_sheet(
    case_dir: tuple[Path, MemoryKeyStore],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder, keystore = case_dir
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    with open_case(folder, PASSPHRASE, keystore) as case:
        sha = case.import_evidence(photo_file(tmp_path / "in")).sha256
    assert main(["extract", str(folder), "--evidence", sha, "--finger-position", "3", "--source-agency", "Lab A"]) == 0
    job_id = capsys.readouterr().out.split("job ")[1].split(":")[0]
    assert main(["report", str(folder), job_id, "--cover", str(tmp_path / "cover.html")]) == 0
    assert "submission cover sheet" in capsys.readouterr().out
    assert "3: right middle" in (tmp_path / "cover.html").read_text(encoding="utf-8")
    assert main(["extract", str(folder), "--evidence", sha, "--finger-position", "11"]) == 1
    assert "finger_position" in capsys.readouterr().err

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    job = rpc("job.run", {"evidence": sha, "finger_position": 9, "source_agency": "Lab B"})["result"]
    assert job["submission"]["finger"] == "left ring"
    assert rpc("job.run", {"evidence": sha, "finger_position": 11})["error"]
    reply = rpc("cover.export", {"job_id": job["job_id"], "dest": str((tmp_path / "gui-cover.html").resolve())})
    assert reply["result"]["job_id"] == job["job_id"]
    assert "Lab B" in (tmp_path / "gui-cover.html").read_text(encoding="utf-8")
    session.close()
