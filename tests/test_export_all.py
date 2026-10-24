"""Exporting every item of one role: a new folder, one logged export each, an index, safe names."""

from __future__ import annotations

import csv
import getpass
import json
import os
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common
from ridge.case.case_model import StoredItem
from ridge.case.cli import main
from ridge.case.export_all import INDEX, export_role, file_name, file_names
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import open_case
from ridge.errors import OutputError, OutputExistsError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    folder = new_case(store, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        run_extraction_job(case, evidence.sha256, signer, JobParams())
        run_extraction_job(case, evidence.sha256, signer, JobParams(flip=True))
    return folder, keystore


def test_every_export_is_written_logged_and_listed(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        written = export_role(case, "export", tmp_path / "out")
        logged = [e for e in case.entries if e["action"] == "artefact.export"]
        with pytest.raises(OutputExistsError):
            export_role(case, "export", tmp_path / "out")
        with pytest.raises(ParameterError, match="one of"):
            export_role(case, "secrets", tmp_path / "other")
        with pytest.raises(ParameterError, match="no reference items"):
            export_role(case, "reference", tmp_path / "none")
    assert len(written) == 2
    assert len(logged) == 2
    assert len({w.name for w in written}) == 2  # the same label, different hashes: unique names
    with (tmp_path / "out" / INDEX).open(encoding="utf-8") as index:
        rows = list(csv.DictReader(index))
    assert {r["sha256"] for r in rows} == {w.item.sha256 for w in written}
    assert all((tmp_path / "out" / r["file"]).is_file() for r in rows)


def test_names_and_index_cells_are_safe(tmp_path: Path) -> None:
    item = StoredItem("ab" * 32, "export", 1, "../../=evil name?.png", None)
    name = file_name(item)
    assert "/" not in name
    assert ".." not in name
    assert name.endswith("_abababababab.png")


def test_names_stay_distinct_when_prefixes_or_case_collide() -> None:
    first = StoredItem("ab" * 32, "export", 1, "print.png")
    same_prefix = StoredItem("ab" * 6 + "cd" * 26, "export", 1, "print.png")
    other_case = StoredItem("ab" * 32, "export", 1, "PRINT.png")
    again = StoredItem("ab" * 32, "export", 1, "Print.png")
    names = file_names([first, same_prefix, other_case, again])
    assert len({n.lower() for n in names}) == 4
    assert names[1] == f"print_{same_prefix.sha256}.png"  # the full hash breaks the tie
    assert names[3] == f"Print_{'ab' * 32}-2.png"  # and a counter after that


def test_a_failed_export_part_way_is_reported_and_indexed(
    case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        real = case.export
        calls: list[str] = []

        def fail_second(sha256: str, path: Path, *, overwrite: bool = False) -> Any:
            calls.append(sha256)
            if len(calls) == 2:
                raise OutputError("the disk is full")
            return real(sha256, path, overwrite=overwrite)

        monkeypatch.setattr(case, "export", fail_second)
        with pytest.raises(OutputError, match="stopped after 1 of 2 file"):
            export_role(case, "export", tmp_path / "half")
        calls.clear()
        calls.append("pretend the first already failed")
        with pytest.raises(OutputError, match="the disk is full"):
            export_role(case, "print", tmp_path / "none")
    with (tmp_path / "half" / INDEX).open(encoding="utf-8") as index:
        rows = list(csv.DictReader(index))
    assert len(rows) == 1  # exactly the file that was exported
    assert (tmp_path / "half" / rows[0]["file"]).is_file()
    assert not (tmp_path / "none").exists()  # nothing was exported: no folder is left
    if os.name == "posix":
        assert (tmp_path / "half").stat().st_mode & 0o077 == 0  # private folder


def test_cli(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder, keystore = case_dir
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    assert main(["export-all", str(folder), "--to", str(tmp_path / "prints"), "--role", "print"]) == 0
    assert len(list((tmp_path / "prints").glob("*.png"))) == 2


def test_a_label_cannot_become_a_spreadsheet_formula(tmp_path: Path) -> None:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    with open_case(new_case(store, keystore), PASSPHRASE, keystore) as case:
        case.import_evidence(photo_file(tmp_path / "in", filename="=HYPERLINK(1).png"))
        export_role(case, "evidence", tmp_path / "out")
    with (tmp_path / "out" / INDEX).open(encoding="utf-8") as index:
        row = next(csv.DictReader(index))
    assert row["label"].startswith("'=")


def test_sidecar(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    unlock = {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE}
    rpc("session.unlock", unlock)
    reply = rpc("case.export_all", {"role": "export", "dest": str((tmp_path / "gui").resolve())})
    assert reply["result"]["files"] == 2
    assert rpc("case.export_all", {"role": "secrets", "dest": str((tmp_path / "x").resolve())})["error"]
    session.close()
