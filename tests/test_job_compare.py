"""Comparing two jobs' settings: only differences, no ranking, the reads logged."""

from __future__ import annotations

import getpass
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.job_compare import differences, render_differences, setting_text
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import open_case
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


def test_only_differing_settings_are_listed() -> None:
    a = {"input": {"sha256": "e" * 64}, "ridge": {"version": "0.2.0"}, "parameters": {"flip": False, "period": None}}
    b = {**a, "parameters": {"flip": True, "period": None, "roi": [1, 2, 3, 4]}}
    rows, same = differences(a, b)
    assert rows == [("flip", "false", "true"), ("roi", "none", "[1,2,3,4]")]
    assert same == 4
    assert differences(a, a)[0] == []
    assert "same input and settings" in render_differences("a" * 8, "b" * 8, [], 5)[0]
    assert setting_text({"b": 1, "a": None}) == '{"a":null,"b":1}'


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    keystore = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    case_dir = new_case(store, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        first = run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id
        second = run_extraction_job(case, evidence.sha256, signer, JobParams(flip=True)).job_id
    assert main(["compare-jobs", str(case_dir), first[:8], second[:8]]) == 0
    shown = capsys.readouterr().out
    assert "flip" in shown
    assert "does not rank the outputs" in shown
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        reads = [e for e in case.entries if e["action"] == "report.read"]
    assert {e["job_id"] for e in reads} == {first, second}
