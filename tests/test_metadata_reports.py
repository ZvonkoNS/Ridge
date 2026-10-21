"""Photo metadata in signed job reports, readable copies and the sidecar (FR-36); outputs stay metadata-free (FR-12)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.metadata_render import DISCLOSURE, NOT_RECORDED, map_url, metadata_html, metadata_text
from ridge.case.report_html import render_report_html
from ridge.case.reports import load_report, render_report
from ridge.case.store import open_case
from ridge.metadata import read_metadata
from ridge.sidecar.handlers import METHODS, Session
from ridge.sidecar.protocol import APPLICATION_ERROR, INVALID_PARAMS
from tests import metadata_samples as samples
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.metadata_samples import MAP_URL
from tests.test_sidecar_gui_methods import call, error_code, result


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def store(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    path = tmp_path / "store"
    create_identity(path, PASSPHRASE, keystore, FAST_KDF)
    return path


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "in" / "finger_gps.png"
    path.parent.mkdir()
    path.write_bytes(samples.finger_png_with_gps())
    return path


@pytest.fixture
def job(store: Path, keystore: MemoryKeyStore, photo: Path) -> dict[str, Any]:
    """Run one job on the GPS-tagged synthetic finger and return what the tests need."""
    case_dir = new_case(store, keystore)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
        signed = load_report(case, store, outcome.job_id)  # hash and signature checked
        outputs = {o.role: case.read(o.sha256, log=False) for o in outcome.outputs}
    return {"report": outcome.report, "signed": signed, "outputs": outputs, "key_id": signer.key_id}


def test_the_signed_report_records_the_metadata_of_the_photo(job: dict[str, Any], photo: Path) -> None:
    recorded = job["signed"].report["input"]["metadata"]
    assert recorded == read_metadata(photo.read_bytes())
    assert recorded["location"]["map_url"] == MAP_URL
    assert recorded["summary"][0] == {
        "name": "Camera",
        "id": "EXIF Make, Model",
        "value": "Synthetic Camera Co Model 7",
    }
    assert job["report"] == job["signed"].report


def test_output_images_carry_none_of_the_metadata(job: dict[str, Any]) -> None:
    assert {"print", "export"} <= set(job["outputs"])
    for role in ("print", "export"):
        data = job["outputs"][role]
        for marker in (b"Synthetic Camera Co", b"SN-0001", b"Exif", b"eXIf", b"WGS-84"):
            assert marker not in data, (role, marker)
        with Image.open(io.BytesIO(data)) as im:
            assert len(im.getexif()) == 0
            assert "exif" not in im.info


def test_the_text_report_appends_every_entry_and_the_map_link(job: dict[str, Any]) -> None:
    text = render_report(job["signed"].report, job["key_id"])
    assert "Photo metadata" in text
    assert f"Map link      {MAP_URL}" in text
    assert f"              {DISCLOSURE}" in text
    assert "Location      46.0512333, 14.5056778 (EXIF GPS; recorded 46" in text
    assert "[EXIF: GPS]" in text
    assert "  Make (0x010F): Synthetic Camera Co" in text
    assert "  Camera serial number: SN-0001" in text
    assert text.index("Photo metadata") < text.index("Image enhancement only")


def test_the_html_copy_links_to_the_map_and_escapes_every_value(job: dict[str, Any]) -> None:
    page = render_report_html(job["signed"])
    href = MAP_URL.replace("&", "&amp;")
    assert f'<a href="{href}" rel="noopener noreferrer" referrerpolicy="no-referrer">Google Maps</a>' in page
    assert "<h3>EXIF: GPS</h3>" in page
    assert "Synthetic Camera Co" in page
    assert "<script" not in page.lower()
    assert f"<br>{DISCLOSURE}" in page  # the copy-only warning travels with the link


def test_hostile_values_and_forged_locations_render_harmlessly() -> None:
    meta = {
        "notice": "n",
        "location": {"latitude": 999, "longitude": 1, "source": "<b>x</b>", "map_url": "javascript:alert(1)"},
        "summary": [{"name": "<script>", "value": "</td><script>alert(1)</script>"}],
        "groups": [{"title": "<i>g</i>", "entries": [{"name": "n", "id": '"><img src=x>', "value": "&amp;"}]}],
        "embedded": [{"kind": "<k>", "bytes": 5, "sha256": "sha256:00"}],
        "warnings": ["<w>"],
    }
    page = metadata_html(meta)
    assert "<script" not in page
    assert "<img" not in page
    assert "javascript:" not in page
    assert "&lt;script&gt;" in page
    assert "&amp;amp;" in page
    assert "Map link</th><td>not available" in page
    assert map_url({"latitude": True, "longitude": 1}) is None
    assert map_url({"latitude": "46", "longitude": 1}) is None
    assert (
        map_url({"latitude": -90, "longitude": 180}) == MAP_URL.split("query=")[0] + "query=-90.0000000%2C180.0000000"
    )
    lines = metadata_text(meta)
    assert "Map link      not available" in lines


def test_reports_made_before_metadata_was_recorded_say_so() -> None:
    assert metadata_text(None) == [f"Photo metadata {NOT_RECORDED}"]
    assert "Not recorded in this report." in metadata_html(None)
    empty: dict[str, Any] = {
        "notice": "n",
        "location": None,
        "summary": [],
        "groups": [],
        "embedded": [],
        "warnings": [],
    }
    assert "Location      none recorded" in metadata_text(empty)
    assert "<p>None recorded.</p>" in metadata_html(empty)


# ----------------------------------------------------------------------------- sidecar


@pytest.fixture
def session(store: Path, keystore: MemoryKeyStore) -> Session:
    case_dir = new_case(store, keystore)
    session = Session(keystore_factory=lambda: keystore)
    result(call(session, "session.unlock", {"store": str(store), "case_id": case_dir.name, "passphrase": PASSPHRASE}))
    return session


def test_metadata_get_reads_the_stored_photo_and_logs_the_read(session: Session, photo: Path) -> None:
    assert "metadata.get" in METHODS
    sha = result(call(session, "case.import", {"path": str(photo)}))["sha256"]
    case, _ = session.require()
    before = len(case.entries)
    shown = result(call(session, "metadata.get", {"sha256": sha}))
    assert shown["sha256"] == sha
    assert shown["role"] == "evidence"
    assert shown["metadata"] == read_metadata(photo.read_bytes())
    assert [e["action"] for e in case.entries[before:]] == ["evidence.read"]


def test_metadata_get_shows_references_too(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "in" / "reference.jpg"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(samples.full_jpeg())
    sha = result(call(session, "case.import_reference", {"path": str(path), "source": "NAFIS candidate 3"}))["sha256"]
    shown = result(call(session, "metadata.get", {"sha256": sha[:12]}))
    assert shown["role"] == "reference"
    assert shown["metadata"]["location"]["map_url"] == MAP_URL


def test_metadata_get_refuses_outputs_bad_params_and_a_locked_case(session: Session, photo: Path) -> None:
    sha = result(call(session, "case.import", {"path": str(photo)}))["sha256"]
    done = result(call(session, "job.run", {"evidence": sha}))
    printed = next(o for o in done["outputs"] if o["role"] == "print")
    assert error_code(call(session, "metadata.get", {"sha256": printed["sha256"]})) == APPLICATION_ERROR
    assert error_code(call(session, "metadata.get", {})) == INVALID_PARAMS
    assert error_code(call(session, "metadata.get", {"sha256": sha, "path": "/etc/passwd"})) == INVALID_PARAMS
    assert error_code(call(session, "metadata.get", {"sha256": 5})) == INVALID_PARAMS
    result(call(session, "session.lock"))
    assert error_code(call(session, "metadata.get", {"sha256": sha})) == APPLICATION_ERROR
