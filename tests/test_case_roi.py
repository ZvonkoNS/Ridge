"""Region of interest (proposed FR-35) and evidence source notes (FR-21): recorded, validated, reproducible."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ridge.case.export_step import ExportOptions
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import load_report, render_report
from ridge.case.reproduce import params_from_report, reproduce_job
from ridge.case.store import open_case
from ridge.errors import ParameterError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def run(case_dir: Path, keystore: MemoryKeyStore, photo: Path, params: JobParams, source: str | None = None) -> Any:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo, source=source)
        return run_extraction_job(case, evidence.sha256, signer, params)


def outputs(outcome: Any) -> dict[str, str]:
    return {o.role: o.sha256 for o in outcome.outputs}


def test_whole_photo_roi_changes_nothing(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in")
    plain = run(case_dir, keystore, photo, JobParams())
    w, h = plain.report["input"]["size_px"]
    whole = run(case_dir, keystore, photo, JobParams(roi=(0, 0, w, h)))
    assert outputs(whole) == outputs(plain)
    assert whole.report["parameters"]["roi"] == [0, 0, w, h]
    assert plain.report["parameters"]["roi"] is None


def test_roi_restricts_the_job_and_reproduces(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in", "arch_large_period", "arch.png")
    plain = run(case_dir, keystore, photo, JobParams())
    w, h = plain.report["input"]["size_px"]
    part = run(case_dir, keystore, photo, JobParams(roi=(w // 8, h // 8, 3 * w // 4, 3 * h // 4)))
    assert outputs(part)["print"] != outputs(plain)["print"]
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        again = reproduce_job(case, case_dir.parent, signer, part.job_id)
        text = render_report(load_report(case, case_dir.parent, part.job_id, log=False).report, "k")
    assert again.identical
    assert f"Region        x {w // 8}, y {h // 8}" in text


@pytest.mark.parametrize("roi", [(-1, 0, 100, 100), (0, 0, 31, 100), (0, 0, 100.0, 100), (0, 0, 100)])
def test_malformed_roi_is_refused_before_the_job(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, roi: Any
) -> None:
    with pytest.raises(ParameterError, match="roi"):
        run(case_dir, keystore, photo_file(tmp_path / "in"), JobParams(roi=roi))
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert not any(e["action"] == "job.start" for e in case.entries)  # nothing started, nothing logged


def test_roi_outside_the_photo_fails_the_job(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    with pytest.raises(ParameterError, match="outside"):
        run(case_dir, keystore, photo_file(tmp_path / "in"), JobParams(roi=(0, 0, 100_000, 100)))
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        end = next(e for e in reversed(case.entries) if e["action"] == "job.end")
    assert end["result"] == "failed"
    assert "outside" in end["error"]


@pytest.mark.parametrize("ruler", [(0.0, 0.0, 5000.0, 0.0, 10.0), (-1.0, 0.0, 50.0, 0.0, 10.0)])
def test_ruler_points_off_the_photo_fail_the_job(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, ruler: tuple[float, float, float, float, float]
) -> None:
    with pytest.raises(ParameterError, match=r"ruler point .* lies outside"):
        run(case_dir, keystore, photo_file(tmp_path / "in"), JobParams(export=ExportOptions(ruler=ruler)))
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        (end,) = [e for e in case.entries if e["action"] == "job.end"]
    assert end["result"] == "failed"
    assert "ruler point" in end["error"]


def test_source_note_is_logged_and_reported(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    outcome = run(case_dir, keystore, photo_file(tmp_path / "in"), JobParams(), source="Exhibit 12, phone A")
    assert outcome.report["input"]["source"] == "Exhibit 12, phone A"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = next(i for i in case.items() if i.role == "evidence")
        assert evidence.source == "Exhibit 12, phone A"
        text = render_report(load_report(case, case_dir.parent, outcome.job_id, log=False).report, "k")
    assert "Source        Exhibit 12, phone A" in text
    plain = run(case_dir, keystore, photo_file(tmp_path / "other", "arch_large_period", "arch.png"), JobParams())
    assert "source" not in plain.report["input"]


def test_roi_round_trips_through_the_report() -> None:
    params = JobParams(roi=(1, 2, 300, 400))
    assert params_from_report(params.to_json()) == params
    legacy = {k: v for k, v in params.to_json().items() if k != "roi"}  # reports from before the roi
    assert params_from_report(legacy).roi is None


def test_size_is_reported_after_exif_orientation(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    import cv2  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    from tests.golden_cases import CASES_BY_NAME  # noqa: PLC0415

    bgr = CASES_BY_NAME["whorl_default"].photo()
    h, w = bgr.shape[:2]
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees on display
    path = tmp_path / "rotated.jpg"
    Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path, format="JPEG", quality=95, exif=exif)
    plain = run(case_dir, keystore, path, JobParams())
    assert plain.report["input"]["size_px"] == [h, w]  # the displayed (rotated) photo, not the stored pixels
    whole = run(case_dir, keystore, path, JobParams(roi=(0, 0, h, w)))
    assert outputs(whole) == outputs(plain)


def test_source_notes_are_never_silently_lost(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in")
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        case.import_evidence(photo)
        with pytest.raises(ParameterError, match="without a source note"):
            case.import_evidence(photo, source="Exhibit 4")
        case.import_evidence(photo)  # no note: a plain logged duplicate
        assert case.entries[-1]["result"] == "duplicate"
    other = photo_file(tmp_path / "other", "arch_large_period", "arch.png")
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        case.import_evidence(other, source="Exhibit 5")
        case.import_evidence(other, source="Exhibit 5")  # the same note again is fine
        with pytest.raises(ParameterError, match="'Exhibit 5'"):
            case.import_evidence(other, source="Exhibit 6")
