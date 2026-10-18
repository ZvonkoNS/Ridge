"""Limits of use from the laboratory's validation (PRD §12 item 8): parsing, checks, job reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ridge.case.crypto import sha256_hex
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.limits import FILE, SCHEMA, deviations, load_limits, parse_limits, report_section
from ridge.case.reports import load_report, render_report
from ridge.case.store import open_case
from ridge.errors import InputRejectedError, ParameterError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


def limits_bytes(**fields: Any) -> bytes:
    return json.dumps({"schema": SCHEMA, "source": "Validation report VR-2027-01", **fields}).encode()


GOOD: dict[str, Any] = {
    "measurements": {"ridge_period_px": 9.0, "found_finger": True},
    "export": {"produced": True, "scale": {"method": "ruler", "uncertainty_pct": 0.5}},
    "quality": {"nfiq2": {"computed": True, "score": 55}},
}


def test_a_limits_file_is_parsed_strictly() -> None:
    data = limits_bytes(min_ridge_period_px=6, max_ridge_period_px=20, architectures=["AMD64"], require_ruler=True)
    limits = parse_limits(data)
    assert (limits.source, limits.sha256, limits.architectures) == (
        "Validation report VR-2027-01",
        sha256_hex(data),
        ("AMD64",),
    )
    assert limits.to_json() == {
        "min_ridge_period_px": 6.0,
        "max_ridge_period_px": 20.0,
        "require_ruler": True,
        "architectures": ["AMD64"],
    }


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        b"[]",
        json.dumps({"schema": "other", "source": "x"}).encode(),
        limits_bytes(extra=1),
        limits_bytes(min_nfiq2="30"),
        limits_bytes(min_nfiq2=True),
        limits_bytes(min_ridge_period_px=-1),
        limits_bytes(min_ridge_period_px=30, max_ridge_period_px=10),
        limits_bytes(require_ruler="yes"),
        limits_bytes(architectures="AMD64"),
        limits_bytes(architectures=["a"] * 17),
        json.dumps({"schema": SCHEMA, "source": ""}).encode(),
        json.dumps({"schema": SCHEMA, "source": "a\nb"}).encode(),
    ],
)
def test_malformed_limits_are_refused(data: bytes) -> None:
    with pytest.raises(ParameterError):
        parse_limits(data)


def test_every_limit_is_checked_in_plain_words() -> None:
    limits = parse_limits(
        limits_bytes(
            min_ridge_period_px=10,
            max_scale_uncertainty_pct=0.25,
            min_nfiq2=60,
            require_finger_found=True,
            architectures=["AMD64"],
        )
    )
    fields = {**GOOD, "measurements": {"ridge_period_px": 8.5, "found_finger": False}}
    found = deviations(limits, fields, machine="arm64")
    assert len(found) == 5
    assert any("arm64" in w and "AMD64" in w for w in found)
    assert any("8.50 px is below the minimum of 10 px" in w for w in found)
    assert any("not located" in w for w in found)
    assert any("±0.5 %" in w for w in found)
    assert any("NFIQ 2 score 55 is below the minimum of 60" in w for w in found)
    assert deviations(parse_limits(limits_bytes(max_ridge_period_px=8)), GOOD, machine="AMD64") == [
        "ridge period 9.00 px is above the maximum of 8 px"
    ]


def test_missing_measurements_are_named_not_ignored() -> None:
    limits = parse_limits(limits_bytes(require_ruler=True, min_nfiq2=30))
    fields = {"measurements": GOOD["measurements"], "export": None, "quality": None}
    found = deviations(limits, fields, machine="AMD64")
    assert any("no comparison export" in w for w in found)
    assert any("no NFIQ 2 score" in w for w in found)
    ridge_period = {**GOOD, "export": {"produced": True, "scale": {"method": "ridge-period", "uncertainty_pct": 15}}}
    assert deviations(limits, ridge_period, machine="AMD64")[0].startswith("the export scale comes from ridge-period")


def test_report_section_without_and_with_limits() -> None:
    assert report_section(None, GOOD) == {"configured": False}
    limits = parse_limits(limits_bytes(min_ridge_period_px=5))
    section = report_section(limits, GOOD)
    assert (section["configured"], section["within"], section["warnings"]) == (True, True, [])
    assert section["sha256"] == limits.sha256


def test_load_limits_is_bounded(tmp_path: Path) -> None:
    assert load_limits(tmp_path) is None
    (tmp_path / FILE).write_bytes(b" " * (64 * 1024 + 1))
    with pytest.raises(InputRejectedError):
        load_limits(tmp_path)


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_jobs_record_the_limits_and_their_warnings(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        plain = run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert plain.report["limits_of_use"] == {"configured": False}
        (store / FILE).write_bytes(limits_bytes(min_ridge_period_px=1000, require_ruler=True))
        checked = run_extraction_job(case, evidence.sha256, signer, JobParams())
        section = checked.report["limits_of_use"]
        assert (section["configured"], section["within"]) == (True, False)
        assert any("below the minimum of 1000 px" in w for w in section["warnings"])
        assert any("require a ruler" in w for w in section["warnings"])
        start = next(e for e in case.entries if e["action"] == "job.start" and e["job_id"] == checked.job_id)
        assert start["limits_of_use"] == section["sha256"]
        shown = render_report(load_report(case, store, checked.job_id).report, signer.key_id)
        assert "outside the limits of use" in shown
        assert "below the minimum of 1000 px" in shown


def test_a_malformed_limits_file_stops_jobs_before_they_start(
    case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path
) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    (store / FILE).write_bytes(b"{broken")
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        before = len(case.entries)
        with pytest.raises(ParameterError, match="limits of use"):
            run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert len(case.entries) == before  # nothing was started or logged
