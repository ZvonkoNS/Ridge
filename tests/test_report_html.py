"""Readable HTML reports and the custody-log page: escaped, script-free, logged, read only."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.crypto import sha256_hex
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.notes import add_note
from ridge.case.report_html import CSP, export_report_html, render_report_html
from ridge.case.reports import SignedReport, load_report
from ridge.case.store import open_case
from ridge.errors import OutputExistsError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture(scope="module")
def signed_case(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, MemoryKeyStore, str]:
    root = tmp_path_factory.mktemp("html")
    keystore = MemoryKeyStore()
    store = root / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    case_dir = new_case(store, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(root / "in"), source="Exhibit 12")
        job = run_extraction_job(case, evidence.sha256, signer, JobParams()).job_id
    return case_dir, keystore, job


def test_the_page_renders_the_signed_report(signed_case: tuple[Path, MemoryKeyStore, str], tmp_path: Path) -> None:
    case_dir, keystore, job = signed_case
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        signed = load_report(case, case_dir.parent, job, log=False)
        add_note(case, "Ridge flow unclear\nnear the delta <b>", job_id=job)
        export_report_html(case, case_dir.parent, job, tmp_path / "r.html")
        with pytest.raises(OutputExistsError):
            export_report_html(case, case_dir.parent, job, tmp_path / "r.html")
        logged = [e for e in case.entries if e["action"] == "report.export"]
    page = (tmp_path / "r.html").read_text(encoding="utf-8")
    assert f'content="{CSP}"' in page
    assert sha256_hex(signed.canonical) in page  # names the exact JSON it renders
    assert "Exhibit 12" in page
    assert "does not identify anyone" in page
    assert "<script" not in page
    assert "<img" not in page
    assert logged[-1]["format"] == "html"
    assert "Ridge flow unclear<br>near the delta &lt;b&gt;" in page
    assert "not part of the signed report" in page


def test_hostile_values_are_escaped() -> None:
    report: dict[str, Any] = {
        "job_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "case_reference": "<script>alert(1)</script>",
        "input": {"label": 'x" onmouseover="alert(1)', "sha256": "a" * 64, "source": "</td><img src=x>"},
        "parameters": {"<b>": "<i>"},
        "outputs": [{"role": "print", "label": "<svg onload=alert(1)>", "sha256": "b" * 64, "size": 1}],
        "disclaimer": "\x1b[2J",
    }
    page = render_report_html(SignedReport(report["job_id"], b"{}", b"", "0123456789abcdef", report))
    for raw in ("<script>alert", "<img src", "<svg", "<b>", 'x" onmouseover', "\x1b"):
        assert raw not in page
    assert "&lt;script&gt;" in page


def test_cli_and_sidecar(
    signed_case: tuple[Path, MemoryKeyStore, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case_dir, keystore, job = signed_case
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    assert main(["report", str(case_dir), job[:8], "--html", str(tmp_path / "cli.html")]) == 0
    assert "the signed JSON stays authoritative" in capsys.readouterr().out
    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(case_dir.parent.resolve()), "case_id": case_dir.name, "passphrase": PASSPHRASE})
    dest = str((tmp_path / "gui.html").resolve())
    assert rpc("report.export_html", {"job_id": job, "dest": dest})["result"]["job_id"] == job
    page = rpc("log.entries", {"limit": 2})["result"]
    assert len(page["entries"]) == 2
    assert page["entries"][0]["seq"] > page["entries"][1]["seq"]  # newest first
    jobs = rpc("log.entries", {"action": "job"})["result"]
    assert {e["action"] for e in jobs["entries"]} <= {"job.start", "job.end"}
    assert jobs["total"] == 2
    assert rpc("log.entries", {"limit": 501})["error"]["code"] < 0
    found = rpc("log.entries", {"text": job[:8]})["result"]
    assert found["total"] >= 2  # job.start and job.end name the job
    assert all(job in json.dumps(e) for e in found["entries"])
    assert rpc("log.entries", {"text": ""})["error"]["code"] < 0
    session.close()
