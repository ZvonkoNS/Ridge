"""Minutiae inside case jobs (PRD FR-40): stored, summarised, mapped into export space."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ridge import extract_fingerprint
from ridge.case.export_step import ExportOptions
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import open_case
from ridge.image_io import load_image
from ridge.minutiae import extract_minutiae
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def run(case_dir: Path, keystore: MemoryKeyStore, photo: Path, params: JobParams) -> tuple[dict[str, object], bytes]:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(case, evidence.sha256, signer, params)
        stored = next((o for o in outcome.outputs if o.role == "minutiae"), None)
        data = case.read(stored.sha256, log=False) if stored else b""
    return outcome.report, data


def test_minutiae_are_off_by_default(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    report, data = run(case_dir, keystore, photo_file(tmp_path / "in"), JobParams())
    assert "minutiae" not in report
    assert data == b""


def test_minutiae_are_stored_and_summarised(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in", "arch_large_period", "arch.png")
    report, data = run(case_dir, keystore, photo, JobParams(minutiae=True))
    doc = json.loads(data)
    summary = report["minutiae"]
    assert isinstance(summary, dict)
    assert summary["count"] == len(doc["minutiae"]) == summary["endings"] + summary["bifurcations"]
    assert "unvalidated" in summary["label"]
    assert doc["schema"] == "ridge.minutiae/1"
    assert len(doc["export_space"]["minutiae"]) == len(doc["minutiae"])
    direct = extract_fingerprint(load_image(photo))
    expected = extract_minutiae(direct.image, direct.period * direct.output_scale).to_json()["minutiae"]
    assert doc["minutiae"] == expected  # same as the library on the same photo


def test_minutiae_without_export(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    params = JobParams(minutiae=True, export=ExportOptions(enabled=False))
    report, data = run(case_dir, keystore, photo_file(tmp_path / "in"), params)
    assert "export_space" not in json.loads(data)
    assert report["export"] is None
