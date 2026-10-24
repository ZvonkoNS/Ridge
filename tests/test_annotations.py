"""Examiner annotations (FR-55): the signed record, its limits, the annotated export, the report, CLI and sidecar."""

from __future__ import annotations

import getpass
import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ridge.case import cli_common
from ridge.case.annotation_image import export_annotated
from ridge.case.annotations import MAX_MARKS, add_annotation, check_marks, current_annotations, list_annotations
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobOutcome, JobParams, run_extraction_job
from ridge.case.report_html import render_report_html
from ridge.case.reports import load_report
from ridge.case.store import open_case
from ridge.errors import OutputExistsError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyStore:
    shared = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: shared)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    return shared


@pytest.fixture
def job(tmp_path: Path, keystore: MemoryKeyStore) -> tuple[Path, JobOutcome, str, str]:
    """A case with one job; returns the case folder, the outcome, the print's and the evidence's SHA-256."""
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    folder = new_case(store, keystore)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
        print_sha = next(i.sha256 for i in case.items() if i.role == "print" and i.job_id == outcome.job_id)
    return folder, outcome, print_sha, evidence.sha256


def test_a_set_is_logged_signed_and_listed(job: tuple[Path, JobOutcome, str, str], keystore: MemoryKeyStore) -> None:
    folder, outcome, print_sha, _ = job
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    marks = [{"x": 10, "y": 20, "kind": "ending", "label": "core side"}, {"x": 30, "y": 40, "kind": "bifurcation"}]
    with open_case(folder, PASSPHRASE, keystore) as case:
        first = add_annotation(
            case, signer, job_id=outcome.job_id, sha256=print_sha[:12], marks=marks, note="first pass"
        )
        assert first.signed_seq == first.seq + 1
        assert case.entries[-1]["action"] == "chain.sign"
        assert case.entries[-2]["action"] == "examiner.annotation"
        assert case.entries[-2]["marks"][0] == {"n": 1, "x": 10, "y": 20, "kind": "ending", "label": "core side"}
        assert (first.role, first.sha256) == ("print", print_sha)
        assert first.width > 0
        assert first.height > 0
        second = add_annotation(
            case, signer, job_id=outcome.job_id, sha256=print_sha, marks=marks[:1], replaces=first.seq
        )
        sets = list_annotations(case.entries, job_id=outcome.job_id)
        assert [a.seq for a in sets] == [first.seq, second.seq]
        assert sets[0].signed_seq == first.seq + 1  # listing recovers the signature that followed
        assert [a.seq for a in current_annotations(case.entries)] == [second.seq]
        assert list_annotations(case.entries, sha256=print_sha)[0].note == "first pass"
        assert list_annotations(case.entries, job_id="no-such-job") == []


def test_refusals(job: tuple[Path, JobOutcome, str, str], keystore: MemoryKeyStore) -> None:
    folder, outcome, print_sha, evidence_sha = job
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    ok = [{"x": 1, "y": 1, "kind": "other"}]
    with open_case(folder, PASSPHRASE, keystore) as case:
        with pytest.raises(ParameterError, match="same job"):
            add_annotation(case, signer, job_id=outcome.job_id, sha256=evidence_sha, marks=ok)
        with pytest.raises(ParameterError, match="same job"):
            add_annotation(case, signer, job_id="0" * 36, sha256=print_sha, marks=ok)
        with pytest.raises(ParameterError, match="outside"):
            add_annotation(
                case, signer, job_id=outcome.job_id, sha256=print_sha, marks=[{"x": 10**6, "y": 1, "kind": "ending"}]
            )
        with pytest.raises(ParameterError, match="not an annotation set"):
            add_annotation(case, signer, job_id=outcome.job_id, sha256=print_sha, marks=ok, replaces=1)
        before = len(case.entries)
    assert before > 0
    with pytest.raises(ParameterError, match="kind"):
        check_marks([{"x": 1, "y": 1, "kind": "ridge"}], 100, 100)
    with pytest.raises(ParameterError, match="whole pixels"):
        check_marks([{"x": 1.5, "y": 1, "kind": "ending"}], 100, 100)
    with pytest.raises(ParameterError, match="whole pixels"):
        check_marks([{"x": True, "y": 1, "kind": "ending"}], 100, 100)
    with pytest.raises(ParameterError, match="label"):
        check_marks([{"x": 1, "y": 1, "kind": "ending", "label": "x" * 41}], 100, 100)
    with pytest.raises(ParameterError, match="label"):
        check_marks([{"x": 1, "y": 1, "kind": "ending", "label": "a" + chr(0x202E) + "b"}], 100, 100)
    with pytest.raises(ParameterError, match="unknown field"):
        check_marks([{"x": 1, "y": 1, "kind": "ending", "angle": 3}], 100, 100)
    with pytest.raises(ParameterError, match=r"1-500"):
        check_marks([], 100, 100)
    with pytest.raises(ParameterError, match=r"1-500"):
        check_marks([{"x": 1, "y": 1, "kind": "ending"}] * (MAX_MARKS + 1), 100, 100)
    assert check_marks([{"x": 1, "y": 1, "kind": "ending", "label": "  "}], 100, 100)[0].label is None


def test_the_annotated_image_is_written_and_logged(
    job: tuple[Path, JobOutcome, str, str], keystore: MemoryKeyStore, tmp_path: Path
) -> None:
    folder, outcome, print_sha, _ = job
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    dest = tmp_path / "out" / "annotated.png"
    dest.parent.mkdir()
    with open_case(folder, PASSPHRASE, keystore) as case:
        a = add_annotation(
            case,
            signer,
            job_id=outcome.job_id,
            sha256=print_sha,
            marks=[
                {"x": 15, "y": 15, "kind": "ending"},
                {"x": 40, "y": 40, "kind": "bifurcation"},
                {"x": 60, "y": 20, "kind": "other"},
            ],
        )
        done = export_annotated(case, a.seq, dest)
        assert done.written_sha256 == hashlib.sha256(dest.read_bytes()).hexdigest()
        assert done.marks == 3
        entry = case.entries[-1]
        assert entry["action"] == "annotation.export"
        assert (entry["annotation_seq"], entry["sha256"], entry["written_sha256"], entry["file"]) == (
            a.seq,
            print_sha,
            done.written_sha256,
            "annotated.png",
        )
        with Image.open(BytesIO(dest.read_bytes())) as im:
            assert im.size == (a.width, a.height)
            assert im.mode == "RGB"
            assert im.getpixel((15 + 6, 15)) != im.getpixel((a.width - 2, a.height - 2))  # something was drawn
        with pytest.raises(OutputExistsError):
            export_annotated(case, a.seq, dest)
        assert (
            export_annotated(case, a.seq, dest, overwrite=True).written_sha256 == done.written_sha256
        )  # deterministic
        with pytest.raises(ParameterError, match="not an annotation set"):
            export_annotated(case, 1, tmp_path / "out" / "x.png")
        with pytest.raises(ParameterError, match="PNG"):
            export_annotated(case, a.seq, tmp_path / "out" / "x.tif")


def test_the_readable_report_lists_the_sets(job: tuple[Path, JobOutcome, str, str], keystore: MemoryKeyStore) -> None:
    folder, outcome, print_sha, _ = job
    signer = unlock_identity(folder.parent, PASSPHRASE, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        a = add_annotation(
            case,
            signer,
            job_id=outcome.job_id,
            sha256=print_sha,
            marks=[{"x": 5, "y": 6, "kind": "ending", "label": "<b>"}],
            note="x < y",
        )
        signed = load_report(case, folder.parent, outcome.job_id, log=False)
        page = render_report_html(signed, [], list_annotations(case.entries, job_id=outcome.job_id))
    assert "Examiner annotations" in page
    assert f"#{a.seq}" in page
    assert "1: ending at (5, 6) &lt;b&gt;" in page
    assert "x &lt; y" in page
    assert f"signed by entry #{a.signed_seq}" in page
    assert "not a match" in page
    assert "<b>" not in page.split("Examiner annotations")[1]


def test_cli_and_sidecar(
    job: tuple[Path, JobOutcome, str, str], keystore: MemoryKeyStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder, outcome, print_sha, _ = job
    assert (
        main(
            [
                "annotate",
                str(folder),
                "--job",
                outcome.job_id,
                "--image",
                print_sha[:12],
                "--mark",
                "10,20,ending,core",
                "--mark",
                "30,40,bifurcation",
                "--note",
                "cli",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "recorded with 2 marks, signed by entry #" in out
    assert main(["annotations", str(folder), "--job", outcome.job_id]) == 0
    text = capsys.readouterr().out
    assert "1: ending at (10, 20)  core" in text
    assert "signed by #" in text
    assert main(["annotations", str(folder), "--json"]) == 0
    sets = json.loads(capsys.readouterr().out)
    assert sets[0]["marks"][1] == {"n": 2, "x": 30, "y": 40, "kind": "bifurcation", "label": None}
    seq = sets[0]["seq"]
    assert main(["export-annotated", str(folder), str(seq), "--to", str(tmp_path / "a.png")]) == 0
    assert (tmp_path / "a.png").is_file()
    assert main(["annotate", str(folder), "--job", outcome.job_id, "--image", print_sha, "--mark", "1,2"]) != 0

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    response = rpc(
        "annotation.add",
        {"job_id": outcome.job_id, "sha256": print_sha, "marks": [{"x": 3, "y": 4, "kind": "other"}], "replaces": seq},
    )
    assert "result" in response, response
    added = response["result"]
    assert added["replaces"] == seq
    assert added["signed_seq"] == added["seq"] + 1
    listed = rpc("annotations.list", {"job_id": outcome.job_id})["result"]
    assert [a["seq"] for a in listed] == [seq, added["seq"]]
    assert (
        rpc("annotation.add", {"job_id": outcome.job_id, "sha256": print_sha, "marks": "x"})["error"]["code"] == -32602
    )
    assert (
        rpc(
            "annotation.add",
            {"job_id": outcome.job_id, "sha256": print_sha, "marks": [{"x": 1, "y": 1, "kind": "fork"}]},
        )["error"]["code"]
        == -32000
    )
    exported = rpc("annotation.export", {"seq": added["seq"], "dest": str((tmp_path / "b.png").resolve())})["result"]
    assert exported["marks"] == 1
    assert (tmp_path / "b.png").is_file()
    assert rpc("annotation.export", {"seq": added["seq"], "dest": "b.png"})["error"]["code"] == -32000
    session.close()
