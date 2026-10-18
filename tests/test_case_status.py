"""The case summary: counts and dates from the custody log, nothing decrypted or logged."""

from __future__ import annotations

import getpass
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.case_status import case_status
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.notes import add_note
from ridge.case.store import open_case
from ridge.case.verify import verify_case
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


def test_status_counts_and_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    case_dir = new_case(store, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert case_status(case).last_verified is None
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        job = run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id
        add_note(case, "synthetic", job_id=job)
        verify_case(case, store)
        before = len(case.entries)
        status = case_status(case)
        assert len(case.entries) == before  # reading the summary logs nothing
    assert status.items["evidence"] == 1
    assert (status.jobs, status.signed_reports, status.notes) == ({"ok": 1}, 1, 1)
    assert (status.last_verify_result, status.retention_reached) == ("ok", False)
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    assert main(["status", str(case_dir)]) == 0
    shown = capsys.readouterr().out
    assert "1 signed report(s)" in shown
    assert "Verified" in shown
