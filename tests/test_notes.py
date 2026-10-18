"""Examiner notes: append-only, validated, tied to jobs and items, corrections keep the original."""

from __future__ import annotations

import getpass
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity
from ridge.case.notes import MAX_CHARS, add_note, clean_note, list_notes
from ridge.case.store import open_case
from ridge.errors import CaseError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def case(tmp_path: Path) -> tuple[Path, MemoryKeyStore, str, str]:
    keystore = MemoryKeyStore()
    create_identity(tmp_path / "store", PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(tmp_path / "store", keystore)
    job_id = str(uuid.uuid4())
    with open_case(case_dir, PASSPHRASE, keystore) as opened:
        item = opened.import_evidence(photo_file(tmp_path / "in"))
        opened.entries.append(opened.custody.append("job.start", job_id=job_id, evidence_sha256=item.sha256))
    return case_dir, keystore, job_id, item.sha256


def test_notes_are_logged_and_corrections_keep_the_original(case: tuple[Path, MemoryKeyStore, str, str]) -> None:
    case_dir, keystore, job_id, sha = case
    with open_case(case_dir, PASSPHRASE, keystore) as opened:
        first = add_note(opened, "  Region chosen to leave out the nail fold.\r\nSecond line.  ", job_id=job_id)
        about_item = add_note(opened, "Photo slightly blurred at the tip.", sha256=sha[:12])
        fix = add_note(opened, "Region left out the nail fold and the crease.", corrects=first.seq)
        add_note(opened, "Case-level remark.")
    assert first.text == "Region chosen to leave out the nail fold.\nSecond line."
    assert about_item.sha256 == sha  # a prefix is resolved to the full hash
    assert (fix.corrects, fix.job_id) == (first.seq, job_id)  # a correction stays with its job
    with open_case(case_dir, PASSPHRASE, keystore) as opened:
        item_fix = add_note(opened, "Blur is at the tip only.", corrects=about_item.seq)
        assert item_fix.sha256 == sha  # and with its photo
        assert [n.seq for n in list_notes(opened.entries, sha256=sha)] == [about_item.seq, item_fix.seq]
    with open_case(case_dir, PASSPHRASE, keystore) as opened:  # survives reopening: it is in the custody log
        everything = list_notes(opened.entries)
        for_job = list_notes(opened.entries, job_id=job_id)
    assert everything[0].text == first.text  # the original is still there
    assert len(everything) == 5
    assert [n.seq for n in for_job] == [first.seq, fix.seq]


@pytest.mark.parametrize(
    "text",
    ["", "   ", "x" * (MAX_CHARS + 1), "bell\x07", "esc\x1b[31m", "cr\ronly", "abc\u202edcb", "iso\u2066late"],
)
def test_unprintable_or_disguised_text_is_refused(text: str) -> None:
    with pytest.raises(ParameterError):
        clean_note(text)


def test_notes_must_refer_to_something_in_the_case(case: tuple[Path, MemoryKeyStore, str, str]) -> None:
    case_dir, keystore, _, _ = case
    with open_case(case_dir, PASSPHRASE, keystore) as opened:
        before = len(opened.entries)
        with pytest.raises(ParameterError, match="no job"):
            add_note(opened, "text", job_id=str(uuid.uuid4()))
        with pytest.raises(CaseError):
            add_note(opened, "text", sha256="0" * 64)
        with pytest.raises(ParameterError, match="not a note"):
            add_note(opened, "text", corrects=0)  # entry 0 exists but is not a note
        assert len(opened.entries) == before  # nothing was logged


def test_cli_and_sidecar(
    case: tuple[Path, MemoryKeyStore, str, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case_dir, keystore, job_id, _ = case
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    assert main(["note", str(case_dir), "Line one\nline two", "--job", job_id]) == 0
    assert "note #" in capsys.readouterr().out
    assert main(["notes", str(case_dir)]) == 0
    shown = capsys.readouterr().out
    assert f"(job {job_id})" in shown
    assert "    Line one\n    line two" in shown
    assert main(["note", str(case_dir), "bad\x1b[2J"]) == 1
    session = Session(keystore_factory=lambda: keystore)
    unlock = {"store": str(case_dir.parent.resolve()), "case_id": case_dir.name, "passphrase": PASSPHRASE}

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", unlock)
    added = rpc("note.add", {"text": "From the GUI", "job_id": job_id})["result"]
    assert added["job_id"] == job_id
    listed = rpc("notes.list", {"job_id": job_id})["result"]
    assert [n["text"] for n in listed] == ["Line one\nline two", "From the GUI"]
    assert rpc("note.add", {"text": 5})["error"]["code"] == -32602
    session.close()
