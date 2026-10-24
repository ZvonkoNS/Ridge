"""Exports of stored items with TIFF/BMP conversion (PRD FR-32): logged with the written file's hash."""

from __future__ import annotations

import csv
import getpass
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.export_all import INDEX, export_role
from ridge.case.export_file import converted_name, export_item
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import open_case
from ridge.errors import ParameterError
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
        run_extraction_job(case, evidence.sha256, signer, JobParams(minutiae=True))
    return folder, keystore


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_an_image_output_is_converted_and_logged_with_both_hashes(
    case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path
) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        gray = next(i for i in case.items() if i.role == "export-gray")
        done = export_item(case, gray.sha256, tmp_path / "afis.tif")
        entry = case.entries[-1]
        assert done.format == "tiff"
        assert done.sha256 == sha(tmp_path / "afis.tif") != gray.sha256
        assert (entry["action"], entry["sha256"], entry["format"], entry["written_sha256"]) == (
            "artefact.export",
            gray.sha256,
            "tiff",
            done.sha256,
        )
        with Image.open(tmp_path / "afis.tif", formats=["TIFF"]) as im:
            assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)
        bmp = export_item(case, gray.sha256, tmp_path / "afis.bmp")
        assert bmp.format == "bmp"
        assert (tmp_path / "afis.bmp").read_bytes().startswith(b"BM")
        # a PNG name or a non-image item: the stored bytes, logged as before
        plain = export_item(case, gray.sha256, tmp_path / "copy.png")
        assert (plain.format, plain.sha256) == (None, gray.sha256)
        assert "format" not in case.entries[-1]
        minutiae = next(i for i in case.items() if i.role == "minutiae")
        raw = export_item(case, minutiae.sha256, tmp_path / "minutiae.tif")
        assert raw.format is None
        assert json.loads((tmp_path / "minutiae.tif").read_text(encoding="utf-8"))["schema"] == "ridge.minutiae/1"


def test_the_print_has_no_resolution_so_it_stays_png(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        print_item = next(i for i in case.items() if i.role == "print")
        before = len(case.entries)
        with pytest.raises(ParameterError, match="records no resolution"):
            export_item(case, print_item.sha256, tmp_path / "print.tif")
        assert len(case.entries) == before  # nothing written, nothing logged
        assert not (tmp_path / "print.tif").exists()
        assert export_item(case, print_item.sha256, tmp_path / "print.png").format is None


def test_converted_names() -> None:
    assert converted_name("a_comparison_500ppi.png", "tiff", "export") == "a_comparison_500ppi.tif"
    assert converted_name("a_comparison_500ppi.png", "bmp", "export-gray") == "a_comparison_500ppi.bmp"
    assert converted_name("a_comparison_500ppi.png", "png", "export") == "a_comparison_500ppi.png"
    assert converted_name("a_minutiae.json", "tiff", "minutiae") == "a_minutiae.json"
    assert converted_name("noext", "tiff", "export") == "noext.tif"


def test_bulk_export_with_a_format(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        written = export_role(case, "export-gray", tmp_path / "tiffs", fmt="tiff")
        with pytest.raises(ParameterError, match="one of"):
            export_role(case, "export", tmp_path / "x", fmt="jp2")  # type: ignore[arg-type]  # the refusal is the point
    assert [w.name.endswith(".tif") for w in written] == [True]
    with (tmp_path / "tiffs" / INDEX).open(encoding="utf-8") as index:
        rows = list(csv.DictReader(index))
    assert rows[0]["format"] == "tiff"
    assert rows[0]["written_sha256"] == sha(tmp_path / "tiffs" / rows[0]["file"]) != rows[0]["sha256"]
    with open_case(folder, PASSPHRASE, keystore) as case:
        plain = export_role(case, "export", tmp_path / "pngs")
    assert plain[0].file.format is None
    with (tmp_path / "pngs" / INDEX).open(encoding="utf-8") as index:
        row = next(csv.DictReader(index))
    assert (row["format"], row["written_sha256"]) == ("as stored", row["sha256"])


def test_cli_export_formats(
    case_dir: tuple[Path, MemoryKeyStore],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder, keystore = case_dir
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    with open_case(folder, PASSPHRASE, keystore) as case:
        gray = next(i.sha256 for i in case.items() if i.role == "export-gray")
    assert main(["export", str(folder), gray, "--to", str(tmp_path / "out.tif")]) == 0
    out = capsys.readouterr().out
    assert "as tiff" in out
    assert sha(tmp_path / "out.tif") in out
    assert main(["export", str(folder), gray, "--to", str(tmp_path / "out.png")]) == 0
    assert "as " not in capsys.readouterr().out.split("exported to")[1]
    assert (
        main(["export-all", str(folder), "--to", str(tmp_path / "bulk"), "--role", "export-gray", "--format", "bmp"])
        == 0
    )
    assert len(list((tmp_path / "bulk").glob("*.bmp"))) == 1


def test_sidecar_export_reports_the_format(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    gray = next(i["sha256"] for i in rpc("case.items", {})["result"] if i["role"] == "export-gray")
    reply = rpc("case.export", {"sha256": gray, "dest": str((tmp_path / "gui.tif").resolve())})["result"]
    assert reply["format"] == "tiff"
    assert reply["sha256"] == sha(tmp_path / "gui.tif")
    bulk = rpc(
        "case.export_all", {"role": "export-gray", "dest": str((tmp_path / "gui-bulk").resolve()), "format": "bmp"}
    )
    assert (bulk["result"]["files"], bulk["result"]["format"]) == (1, "bmp")
    assert rpc("case.export_all", {"role": "export", "dest": str((tmp_path / "x").resolve()), "format": "jp2"})["error"]
    session.close()
