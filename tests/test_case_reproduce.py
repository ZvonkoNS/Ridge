"""Reproduction from the report alone (PRD FR-34, NFR-3): identical re-runs, logged mismatches."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ridge.case import jobs
from ridge.case.export_step import ExportOptions
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import list_jobs
from ridge.case.reproduce import params_from_report, reproduce_job
from ridge.case.store import open_case
from ridge.case.verify import verify_case
from ridge.errors import IntegrityError, ParameterError
from ridge.pipeline import extract_fingerprint
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def first_job(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, params: JobParams) -> str:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        return run_extraction_job(case, evidence.sha256, signer, params).job_id


def reproduce(case_dir: Path, keystore: MemoryKeyStore, job_id: str) -> Any:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return reproduce_job(case, case_dir.parent, signer, job_id[:8])


def test_same_platform_reproduces_bit_for_bit(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    job_id = first_job(case_dir, keystore, tmp_path, JobParams(debug=True, minutiae=True))
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        stored_before = len(case.items())
    result = reproduce(case_dir, keystore, job_id)
    assert result.identical
    assert (result.original_job, result.differing, result.missing, result.extra) == (job_id, [], [], [])
    assert any(m.startswith("debug:") for m in result.matched)
    assert result.environment_changes == {}
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert len(case.items()) == stored_before  # identical outputs are deduplicated
        entry = next(e for e in reversed(case.entries) if e["action"] == "job.reproduce")
        assert (entry["result"], entry["original_job_id"], entry["job_id"]) == ("ok", job_id, result.new_job)
        assert case.entries[-1]["action"] == "chain.sign"
        assert [j.job_id for j in list_jobs(case.entries)] == [job_id, result.new_job]
        assert verify_case(case, case_dir.parent).ok


def test_a_changed_result_is_a_logged_mismatch(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = first_job(case_dir, keystore, tmp_path, JobParams())
    env = jobs.environment()

    def drifted(*args: Any, **kwargs: Any) -> Any:  # stands in for another platform's floating point
        result = extract_fingerprint(*args, **kwargs)
        result.image[0, 0] = np.uint8(255 - int(result.image[0, 0]))
        return result

    monkeypatch.setattr(jobs, "extract_fingerprint", drifted)
    monkeypatch.setattr(jobs, "environment", lambda: {**env, "machine": "not-a-real-architecture"})
    result = reproduce(case_dir, keystore, job_id)
    assert not result.identical
    assert any(d.startswith("print:") for d in result.differing)
    assert result.environment_changes["machine"][1] == "not-a-real-architecture"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        entry = next(e for e in reversed(case.entries) if e["action"] == "job.reproduce")
    assert entry["result"] == "mismatch"
    assert entry["environment_changes"]["machine"][1] == "not-a-real-architecture"


def test_missing_and_extra_outputs(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = first_job(case_dir, keystore, tmp_path, JobParams(debug=True))
    from ridge.case import reproduce as module  # noqa: PLC0415

    real = module.params_from_report
    monkeypatch.setattr(module, "params_from_report", lambda p: JobParams(**{**vars(real(p)), "debug": False}))
    result = reproduce(case_dir, keystore, job_id)
    assert result.missing
    assert all(m.startswith("debug:") for m in result.missing)
    assert not result.extra
    assert not result.identical


def test_parameters_round_trip() -> None:
    params = JobParams(period=9.5, flip=True, minutiae=True)
    assert params_from_report(params.to_json()) == params
    ruler = JobParams(export=ExportOptions(ruler=(1.0, 2.0, 3.0, 4.0, 5.0)))
    assert params_from_report(ruler.to_json()) == ruler
    legacy = {k: v for k, v in params.to_json().items() if k != "minutiae"}  # reports from before M3
    assert params_from_report(legacy).minutiae is False
    with pytest.raises(IntegrityError, match="incomplete"):
        params_from_report({"period": None})


def test_unknown_job(case_dir: Path, keystore: MemoryKeyStore) -> None:
    with pytest.raises(ParameterError, match="no job"):
        reproduce(case_dir, keystore, "0" * 8)


def test_a_failed_rerun_is_logged_and_linked(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ridge.errors import NoRidgePatternError  # noqa: PLC0415

    job_id = first_job(case_dir, keystore, tmp_path, JobParams())

    def fails(*args: Any, **kwargs: Any) -> Any:
        raise NoRidgePatternError("no ridge pattern found")

    monkeypatch.setattr(jobs, "extract_fingerprint", fails)
    with pytest.raises(NoRidgePatternError):
        reproduce(case_dir, keystore, job_id)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        entry = next(e for e in reversed(case.entries) if e["action"] == "job.reproduce")
        rerun = list_jobs(case.entries)[-1]
        assert case.entries[-1]["action"] == "chain.sign"
        assert verify_case(case, case_dir.parent).ok
    assert (entry["result"], entry["original_job_id"], entry["job_id"]) == ("failed", job_id, rerun.job_id)
    assert rerun.result == "failed"
    assert "no ridge pattern" in entry["error"]
