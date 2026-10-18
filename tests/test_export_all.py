"""Exporting every item of one role: a new folder, one logged export each, an index, safe names."""

from __future__ import annotations

import csv
import getpass
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.export_all import INDEX, export_role, file_name
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import StoredItem, open_case
from ridge.errors import OutputExistsError, ParameterError
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
    assert len({name for _, name in written}) == 2  # the same label, different hashes: unique names
    with (tmp_path / "out" / INDEX).open(encoding="utf-8") as index:
        rows = list(csv.DictReader(index))
    assert {r["sha256"] for r in rows} == {i.sha256 for i, _ in written}
    assert all((tmp_path / "out" / r["file"]).is_file() for r in rows)


def test_names_and_index_cells_are_safe(tmp_path: Path) -> None:
    item = StoredItem("ab" * 32, "export", 1, "../../=evil name?.png", None)
    name = file_name(item)
    assert "/" not in name
    assert ".." not in name
    assert name.endswith("_abababababab.png")


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
