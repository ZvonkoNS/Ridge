"""``ridge-case metadata``: one stored photo's metadata without a job (FR-36), with synthetic images only."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest
from PIL import Image

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.custody import Entry
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobOutcome, JobParams, run_extraction_job
from ridge.case.metadata_render import DISCLOSURE
from ridge.case.store import open_case
from ridge.metadata import SCHEMA, read_metadata
from tests import metadata_samples as samples
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.metadata_samples import MAP_URL

ESC, RLO = chr(0x1B), chr(0x202E)  # built with chr(): invisible characters never go into the source


@pytest.fixture
def keystore(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyStore:
    shared = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: shared)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    return shared


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def stored(case_dir: Path, keystore: MemoryKeyStore, data: bytes, name: str, *, reference: str | None = None) -> str:
    """Import synthetic image bytes as evidence (or as a reference from `reference`); return the SHA-256."""
    path = case_dir.parent.parent / "in" / name
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(data)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        item = case.import_reference(path, reference) if reference else case.import_evidence(path)
    return item.sha256


def entries(case_dir: Path, keystore: MemoryKeyStore) -> list[Entry]:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return list(case.entries)


def run_job(case_dir: Path, keystore: MemoryKeyStore, sha: str) -> JobOutcome:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return run_extraction_job(case, sha, signer, JobParams())


def test_text_lists_every_entry_with_the_map_link_and_logs_one_read(
    case_dir: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = stored(case_dir, keystore, samples.finger_png_with_gps(), "finger_gps.png")
    before = entries(case_dir, keystore)
    assert main(["metadata", str(case_dir), sha[:12]]) == 0  # a unique prefix is enough
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == [f"evidence {sha}  finger_gps.png", "Photo metadata"]
    assert "Ridge does not verify metadata" in lines[2]
    assert any(line.startswith("Location      46.0512333, 14.5056778 (EXIF GPS; recorded 46") for line in lines)
    link = lines.index(f"Map link      {MAP_URL}")
    assert lines[link + 1] == f"              {DISCLOSURE}"  # Ridge never opens it; opening it tells Google
    assert {"[EXIF: GPS]", "  Make (0x010F): Synthetic Camera Co", "  Camera serial number: SN-0001"} <= set(lines)
    new = entries(case_dir, keystore)[len(before) :]
    assert [(e["action"], e["sha256"]) for e in new] == [("evidence.read", sha)]


def test_json_is_the_record_the_signed_job_report_holds(
    case_dir: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]
) -> None:
    data = samples.finger_png_with_gps()
    sha = stored(case_dir, keystore, data, "finger_gps.png")
    assert main(["metadata", str(case_dir), sha, "--json"]) == 0
    out = capsys.readouterr().out
    record = json.loads(out)
    assert record["schema"] == SCHEMA
    assert record == read_metadata(data)
    assert record == run_job(case_dir, keystore, sha).report["input"]["metadata"]  # comparable with a report


def test_references_are_shown_and_json_output_is_ascii(
    case_dir: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]
) -> None:
    data = samples.iptc_jpeg()  # IPTC text with non-ASCII letters
    sha = stored(case_dir, keystore, data, "candidate.jpg", reference="NAFIS candidate 3")
    before = len(entries(case_dir, keystore))
    assert main(["metadata", str(case_dir), sha[:8], "--json"]) == 0
    out = capsys.readouterr().out
    assert out.isascii()
    assert "\\u0161" in out  # the letter in "Predmet št. 12", escaped
    assert json.loads(out) == read_metadata(data)
    assert main(["metadata", str(case_dir), sha[:8]]) == 0
    shown = capsys.readouterr().out
    assert shown.startswith(f"reference {sha}  candidate.jpg\n")
    assert "Predmet št. 12" in shown
    assert [e["action"] for e in entries(case_dir, keystore)[before:]] == ["reference.read", "reference.read"]


def test_hidden_and_control_characters_never_reach_the_terminal(
    case_dir: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]
) -> None:
    exif = Image.Exif()
    exif[0x010F] = f"Camera{ESC}[2JCo"  # a terminal escape (EXIF text is ASCII)
    packet = samples.xmp(attrs=f'xmp:CreatorTool="Tool{RLO}x"')  # a right-to-left override
    sha = stored(case_dir, keystore, samples.jpeg(exif, xmp_packet=packet, icc=False), f"photo{RLO}gpj.jpg")
    for extra in ([], ["--json"]):
        assert main(["metadata", str(case_dir), sha, *extra]) == 0
        out = capsys.readouterr().out
        assert ESC not in out
        assert RLO not in out
        assert "Camera<U+001B>[2JCo" in out
        assert "Tool<U+202E>x" in out
    assert out.isascii()
    assert main(["metadata", str(case_dir), sha]) == 0
    assert capsys.readouterr().out.startswith(f"evidence {sha}  photo<U+202E>gpj.jpg\n")  # the file name too


def test_outputs_and_unknown_items_are_refused_before_any_read(
    case_dir: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = stored(case_dir, keystore, samples.finger_png_with_gps(), "finger_gps.png")
    outcome = run_job(case_dir, keystore, sha)
    before = entries(case_dir, keystore)
    assert {o.role for o in outcome.outputs} >= {"print", "export"}
    for output in outcome.outputs:
        assert main(["metadata", str(case_dir), output.sha256]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "imported photos only (evidence or reference images)" in captured.err
    for unknown in ("0" * 64, sha[:7]):  # no such item; a prefix shorter than 8 characters
        assert main(["metadata", str(case_dir), unknown, "--json"]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "no unique stored item" in captured.err
    assert entries(case_dir, keystore) == before  # nothing was read, so nothing was logged


def test_a_locked_case_or_a_wrong_passphrase_shows_and_logs_nothing(
    case_dir: Path, keystore: MemoryKeyStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = stored(case_dir, keystore, samples.finger_png_with_gps(), "finger_gps.png")
    before = entries(case_dir, keystore)
    lock = case_dir / "LOCK"
    lock.write_text("open elsewhere", encoding="utf-8")
    assert main(["metadata", str(case_dir), sha]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "is open elsewhere" in captured.err
    lock.unlink()
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "not the right passphrase")
    assert main(["metadata", str(case_dir), sha, "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "wrong passphrase" in captured.err
    assert entries(case_dir, keystore) == before
