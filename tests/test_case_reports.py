"""Jobs and signed reports (PRD FR-28): listing, verified reads, exports, offline checks, tampering."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import rfc8785

from ridge.case import reports
from ridge.case.crypto import sha256_hex
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import (
    JobRecord,
    check_exported_report,
    export_report,
    list_jobs,
    load_report,
    render_report,
    resolve_job,
    signature_path,
)
from ridge.case.store import open_case
from ridge.errors import ExtractionError, InputRejectedError, IntegrityError, OutputExistsError, ParameterError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


@pytest.fixture
def job_id(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> str:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        return run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id


def actions(case_dir: Path, keystore: MemoryKeyStore) -> list[str]:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return [e["action"] for e in case.entries]


# ------------------------------------------------------------------ listing and resolving


def test_list_jobs_covers_every_outcome() -> None:
    entries: list[dict[str, Any]] = [
        {"action": "case.create"},
        {"action": "job.start", "job_id": "a" * 8 + "-1", "sha256": "e1", "ts_utc": "t1"},
        {"action": "report.sign", "job_id": "a" * 8 + "-1", "report_sha256": "r1", "key_id": "k"},
        {"action": "job.end", "job_id": "a" * 8 + "-1", "result": "ok", "ts_utc": "t2"},
        {"action": "job.start", "job_id": "b" * 8 + "-2", "sha256": "e2", "ts_utc": "t3"},
        {"action": "job.end", "job_id": "b" * 8 + "-2", "result": "failed", "error": "no ridges", "ts_utc": "t4"},
        {"action": "job.start", "job_id": "c" * 8 + "-3", "sha256": "e3", "ts_utc": "t5"},  # never closed
        {"action": "job.end", "job_id": "unknown", "result": "ok", "ts_utc": "t6"},  # ignored
    ]
    ok, failed, still_open = list_jobs(entries)
    assert (ok.result, ok.report_sha256, ok.ended_utc) == ("ok", "r1", "t2")
    assert (failed.result, failed.error, failed.report_sha256) == ("failed", "no ridges", None)
    assert (still_open.result, still_open.ended_utc) == ("open", None)
    assert ok.to_json()["evidence_sha256"] == "e1"


def test_resolve_by_prefix_and_refusals(case_dir: Path, keystore: MemoryKeyStore, job_id: str) -> None:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert resolve_job(case.entries, job_id[:8].upper()).job_id == job_id
        for bad in ("", "abc", "../../reports/x", job_id[:8] + "/"):
            with pytest.raises(ParameterError, match="UUID"):
                resolve_job(case.entries, bad)
        with pytest.raises(ParameterError, match="no job"):
            resolve_job(case.entries, "f" * 8 if not job_id.startswith("f" * 8) else "0" * 8)


def test_ambiguous_prefix_and_unsigned_job() -> None:
    entries = [
        {"action": "job.start", "job_id": "12345678-a", "sha256": "e", "ts_utc": "t"},
        {"action": "job.start", "job_id": "12345678-b", "sha256": "e", "ts_utc": "t"},
    ]
    with pytest.raises(ParameterError, match="ambiguous"):
        resolve_job(entries, "12345678")
    with pytest.raises(ParameterError, match="no signed report"):
        resolve_job(entries, "12345678-a")


def test_failed_job_is_listed_without_a_report(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ridge.case import jobs  # noqa: PLC0415

    def fail(*args: object, **kwargs: object) -> None:
        raise ExtractionError("no ridge pattern")

    monkeypatch.setattr(jobs, "extract_fingerprint", fail)
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        with pytest.raises(ExtractionError):
            run_extraction_job(case, evidence.sha256, signer, JobParams())
        (job,) = list_jobs(case.entries)
    assert (job.result, job.error, job.report_sha256) == ("failed", "no ridge pattern", None)


# ------------------------------------------------------------------ verified reads


def test_load_report_verifies_and_logs(case_dir: Path, keystore: MemoryKeyStore, job_id: str) -> None:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        signed = load_report(case, case_dir.parent, job_id)
        unlogged = load_report(case, case_dir.parent, job_id, log=False)
    assert signed.report["job_id"] == job_id
    assert signed.canonical == unlogged.canonical == bytes(rfc8785.dumps(signed.report))
    assert actions(case_dir, keystore).count("report.read") == 1


def test_tampered_report_files_are_refused(case_dir: Path, keystore: MemoryKeyStore, job_id: str) -> None:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        report_path, sig_path = case.report_paths(job_id)
    sig = bytearray(sig_path.read_bytes())
    sig[0] ^= 1
    sig_path.write_bytes(bytes(sig))
    with open_case(case_dir, PASSPHRASE, keystore) as case, pytest.raises(IntegrityError, match="signature"):
        load_report(case, case_dir.parent, job_id)
    sealed = bytearray(report_path.read_bytes())
    sealed[-1] ^= 1
    report_path.write_bytes(bytes(sealed))
    with open_case(case_dir, PASSPHRASE, keystore) as case, pytest.raises(IntegrityError):
        load_report(case, case_dir.parent, job_id)


def test_report_must_match_the_log_and_its_own_job(
    case_dir: Path, keystore: MemoryKeyStore, job_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        canonical, signature = case.get_report(job_id)
        other = json.loads(canonical) | {"case_id": "another-case"}
        forged = bytes(rfc8785.dumps(other))
        forged_signature = signer.sign(forged)  # a validly signed report, but for another case
        monkeypatch.setattr(case, "get_report", lambda _job: (forged, forged_signature))
        with pytest.raises(IntegrityError, match="does not match the custody log"):
            load_report(case, case_dir.parent, job_id)
        real = resolve_job(case.entries, job_id)
        monkeypatch.setattr(reports, "resolve_job", lambda *_: replace(real, report_sha256=sha256_hex(forged)))
        with pytest.raises(IntegrityError, match="another job or case"):
            load_report(case, case_dir.parent, job_id)
        monkeypatch.setattr(reports, "resolve_job", lambda *_: replace(real, key_id="0" * 16))
        monkeypatch.setattr(case, "get_report", lambda _job: (canonical, signature))
        with pytest.raises(IntegrityError, match="unknown key"):
            load_report(case, case_dir.parent, job_id)


# ------------------------------------------------------------------ exports and offline checks


def export(case_dir: Path, keystore: MemoryKeyStore, job_id: str, dest: Path) -> bytes:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return export_report(case, case_dir.parent, job_id, dest).canonical


def test_export_and_check_offline(case_dir: Path, keystore: MemoryKeyStore, job_id: str, tmp_path: Path) -> None:
    dest = tmp_path / "out" / "report.json"
    dest.parent.mkdir()
    canonical = export(case_dir, keystore, job_id, dest)
    assert dest.read_bytes() == canonical
    assert len(base64.b64decode(signature_path(dest).read_text(encoding="ascii"))) == 64
    assert "report.export" in actions(case_dir, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        logged = [e for e in case.entries if e["action"] == "report.export"][-1]
        signed_hash = next(j.report_sha256 for j in list_jobs(case.entries) if j.job_id == job_id)
    assert logged["sha256"] == sha256_hex(dest.read_bytes()) == signed_hash  # the bytes written, as signed

    check = check_exported_report(dest)
    assert (check.job_id, check.key_confirmed) == (job_id, False)
    assert check_exported_report(dest, expected_key_id=check.key_id.upper()).key_confirmed is True
    with pytest.raises(IntegrityError, match="not by the expected key"):
        check_exported_report(dest, expected_key_id="0" * 16)

    with pytest.raises(OutputExistsError):
        export(case_dir, keystore, job_id, dest)
    dest.unlink()
    with pytest.raises(OutputExistsError):  # the signature alone also blocks a silent overwrite
        export(case_dir, keystore, job_id, dest)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        export_report(case, case_dir.parent, job_id, dest, overwrite=True)
    assert dest.read_bytes() == canonical


def exported(case_dir: Path, keystore: MemoryKeyStore, job_id: str, tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    dest = tmp_path / "report.json"
    canonical = export(case_dir, keystore, job_id, dest)
    return dest, json.loads(canonical)


def test_changed_exports_fail_the_offline_check(
    case_dir: Path, keystore: MemoryKeyStore, job_id: str, tmp_path: Path
) -> None:
    dest, report = exported(case_dir, keystore, job_id, tmp_path)
    original = dest.read_bytes()
    edited = report | {"measurements": {**report["measurements"], "ridge_period_px": 99.0}}
    dest.write_bytes(bytes(rfc8785.dumps(edited)))
    with pytest.raises(IntegrityError, match="does not verify"):
        check_exported_report(dest)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with pytest.raises(IntegrityError, match="canonical form"):
        check_exported_report(dest)
    dest.write_bytes(original)
    signature_path(dest).write_text("not base64!", encoding="ascii")
    with pytest.raises(IntegrityError, match="not base64"):
        check_exported_report(dest)


type Change = Callable[[dict[str, Any]], dict[str, Any]]
MALFORMED: dict[str, tuple[Change, str]] = {
    "no signer": (lambda r: r | {"signer": None}, "names no signer"),
    "key id": (lambda r: r | {"signer": {**r["signer"], "key_id": "0" * 16}}, "does not match its public key"),
    "public key": (lambda r: r | {"signer": {**r["signer"], "public_key": "@@"}}, "public key is not base64"),
    "schema": (lambda r: r | {"schema": "something/1"}, "not a ridge.job-report/1 report"),
}


@pytest.mark.parametrize("kind", MALFORMED)
def test_malformed_signer_or_schema(
    case_dir: Path, keystore: MemoryKeyStore, job_id: str, tmp_path: Path, kind: str
) -> None:
    change, message = MALFORMED[kind]
    dest, report = exported(case_dir, keystore, job_id, tmp_path)
    dest.write_bytes(bytes(rfc8785.dumps(change(report))))
    with pytest.raises(IntegrityError, match=message):
        check_exported_report(dest)


def test_offline_check_rejects_non_json_and_oversized_files(tmp_path: Path) -> None:
    report, sig = tmp_path / "r.json", tmp_path / "r.sig"
    sig.write_text(base64.b64encode(b"x" * 64).decode(), encoding="ascii")
    report.write_bytes(b"\xff\xfe not json")
    with pytest.raises(IntegrityError, match="UTF-8 JSON"):
        check_exported_report(report, sig)
    report.write_bytes(b" " * (reports.MAX_REPORT_BYTES + 1))
    with pytest.raises(InputRejectedError):
        check_exported_report(report, sig)


# ------------------------------------------------------------------ rendering


def test_render_report(case_dir: Path, keystore: MemoryKeyStore, job_id: str) -> None:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        signed = load_report(case, case_dir.parent, job_id, log=False)
    text = render_report(signed.report, signed.key_id)
    assert f"Job report {job_id}" in text
    assert "signature verified" in text
    assert "Export        500 ppi" in text
    assert "does not identify anyone" in text

    report = signed.report | {
        "case_reference": "KT\x1b[2J-1",  # a terminal escape must not reach the terminal
        "export": {"produced": False, "reason": "too small"},
        "quality": {"nfiq2": {"computed": True, "score": 61, "label": "indicative", "version": "2.3"}},
        "minutiae": {"produced": True, "count": 3, "endings": 2, "bifurcations": 1, "label": "unvalidated"},
    }
    text = render_report(report, signed.key_id)
    assert "\x1b" not in text
    assert "KT?[2J-1" in text
    assert "not produced: too small" in text
    assert "NFIQ 2        61 (indicative; 2.3)" in text
    assert "Minutiae      3 (2 endings, 1 bifurcations)" in text
    quiet = render_report(
        report | {"export": None, "quality": None, "minutiae": {"produced": False, "reason": "r"}}, "k"
    )
    assert "Export        not requested" in quiet
    assert "Minutiae      not produced: r" in quiet
    assert "NFIQ 2" not in quiet


def test_job_record_is_frozen() -> None:
    record = JobRecord("j", "e", "t", None, "open", None, None, None)
    with pytest.raises(AttributeError):
        record.result = "ok"  # type: ignore[misc]


def test_failed_exports_leave_nothing_behind(
    case_dir: Path, keystore: MemoryKeyStore, job_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ridge.case import case_model as store_module  # noqa: PLC0415  # publish_logged lives here
    from ridge.image_io import publish as real_publish  # noqa: PLC0415

    calls: list[Path] = []

    def second_fails(path: Path, data: bytes, *, overwrite: bool = False) -> None:
        calls.append(path)
        if len(calls) == 2:
            raise OSError("disk full")
        real_publish(path, data, overwrite=overwrite)

    dest = tmp_path / "report.json"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        monkeypatch.setattr(store_module, "publish", second_fails)
        with pytest.raises(OSError, match="disk full"):
            export_report(case, case_dir.parent, job_id, dest)
        monkeypatch.setattr(store_module, "publish", real_publish)
        assert not dest.exists()
        assert not signature_path(dest).exists()

        def no_log(*args: object, **kwargs: object) -> None:
            raise OSError("log unavailable")

        monkeypatch.setattr(case.custody, "append", no_log)
        with pytest.raises(OSError, match="log unavailable"):
            export_report(case, case_dir.parent, job_id, dest)
        assert not dest.exists()
        assert not signature_path(dest).exists()
        print_sha = next(i.sha256 for i in case.items() if i.role == "print")
        with pytest.raises(OSError, match="log unavailable"):
            case.export(print_sha, tmp_path / "print.png")
        assert not (tmp_path / "print.png").exists()
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert not any(e["action"] in ("report.export", "artefact.export") for e in case.entries)
