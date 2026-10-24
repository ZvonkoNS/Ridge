"""Scale sweeps of comparison exports (PRD FR-39): factors over the recorded uncertainty, every file logged."""

from __future__ import annotations

import csv
import getpass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import open_case
from ridge.case.sweep import INDEX, export_sweep
from ridge.errors import ExportTooLargeError, OutputExistsError, ParameterError
from ridge.export.sweep import MAX_STEPS, MIN_STEPS, rescaled, sweep_factors
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


def test_factors_spread_evenly_over_the_uncertainty() -> None:
    assert sweep_factors(15.0) == (0.85, 1.0, 1.15)
    assert sweep_factors(15.0, 5) == (0.85, 0.925, 1.0, 1.075, 1.15)
    assert sweep_factors(0.5, 3) == (0.995, 1.0, 1.005)
    assert len(sweep_factors(10.0, MAX_STEPS)) == MAX_STEPS
    assert (MIN_STEPS, MAX_STEPS) == (3, 9)
    for bad_steps in (2, 4, 1, 11, 3.0, True):
        with pytest.raises(ParameterError, match="odd number"):
            sweep_factors(15.0, bad_steps)  # type: ignore[arg-type]  # the refusal is the point
    for bad_u in (0.0, -1.0, 60.0, float("nan"), float("inf")):
        with pytest.raises(ParameterError):
            sweep_factors(bad_u)


def test_rescaled_sizes_and_determinism() -> None:
    yy, xx = np.mgrid[0:40, 0:60]
    image = ((xx * 4 + yy) % 256).astype(np.uint8)
    smaller = rescaled(image, 0.85)
    larger = rescaled(image, 1.15)
    assert smaller.shape == (34, 51)
    assert larger.shape == (46, 69)
    assert np.array_equal(rescaled(image, 1.0), image)
    assert rescaled(image, 1.0) is not image
    assert np.array_equal(rescaled(image, 0.85), smaller)
    with pytest.raises(ExportTooLargeError):
        rescaled(np.zeros((1000, 1000), np.uint8), 300.0)
    with pytest.raises(ParameterError):
        rescaled(image, 0.0)


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(store, PASSPHRASE, keystore)
    folder = new_case(store, keystore)
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        run_extraction_job(case, evidence.sha256, signer, JobParams())  # ridge-period scale: +-15 %
    return folder, keystore


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sweep_writes_logged_rescaled_copies_at_the_declared_resolution(
    case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path
) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        gray = next(i for i in case.items() if i.role == "export-gray")
        before = len(case.entries)
        sweep = export_sweep(case, folder.parent, gray.sha256, tmp_path / "sweep")
        entries = [e for e in case.entries[before:] if e["action"] == "sweep.export"]
        with pytest.raises(OutputExistsError):
            export_sweep(case, folder.parent, gray.sha256, tmp_path / "sweep")
        print_item = next(i for i in case.items() if i.role == "print")
        with pytest.raises(ParameterError, match="comparison export"):
            export_sweep(case, folder.parent, print_item.sha256, tmp_path / "other")
        assert not (tmp_path / "other").exists()
    assert [f.factor for f in sweep.files] == [0.85, 1.0, 1.15]
    assert sweep.scale["method"] == "ridge-period"
    assert len(entries) == 3
    middle = sweep.files[1]
    assert middle.sha256 == gray.sha256  # factor 1.0 re-encodes the same pixels at the same resolution
    sizes = []
    for f, entry in zip(sweep.files, entries, strict=True):
        path = tmp_path / "sweep" / f.name
        assert f.name.endswith(f"_scale_{f.factor:.4f}.png")
        assert sha(path) == f.sha256 == entry["sha256"]
        assert (entry["source_sha256"], entry["factor"], entry["ppi"]) == (gray.sha256, f.factor, 500.0)
        with Image.open(path) as im:
            assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)  # declared the same at every factor
            sizes.append(im.size)
    assert sizes[0] < sizes[1] < sizes[2]
    with (tmp_path / "sweep" / INDEX).open(encoding="utf-8") as index:
        rows = list(csv.DictReader(index))
    assert [r["factor"] for r in rows] == ["0.8500", "1.0000", "1.1500"]
    assert rows[0]["source_sha256"] == gray.sha256
    assert float(rows[0]["uncertainty_pct"]) == 15.0  # the canonical report writes 15 for 15.0


def test_sweep_formats_and_steps(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    with open_case(folder, PASSPHRASE, keystore) as case:
        export = next(i for i in case.items() if i.role == "export")
        sweep = export_sweep(case, folder.parent, export.sha256, tmp_path / "tiffs", steps=5, fmt="tiff")
        with pytest.raises(ParameterError, match="odd number"):
            export_sweep(case, folder.parent, export.sha256, tmp_path / "x", steps=4)
    assert len(sweep.files) == 5
    assert all(f.name.endswith(".tif") for f in sweep.files)
    with Image.open(tmp_path / "tiffs" / sweep.files[0].name, formats=["TIFF"]) as im:
        assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)


def test_cli_and_sidecar_sweep(
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
    assert main(["sweep", str(folder), gray, "--to", str(tmp_path / "cli")]) == 0
    out = capsys.readouterr().out
    assert "3 file(s) written" in out
    assert "0.8500, 1.0000, 1.1500" in out
    assert "separate searches" in out
    assert len(list((tmp_path / "cli").glob("*.png"))) == 3
    assert main(["sweep", str(folder), gray, "--to", str(tmp_path / "cli"), "--steps", "5"]) == 1
    assert "already exists" in capsys.readouterr().err

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    reply = rpc(
        "sweep.export", {"sha256": gray, "dest": str((tmp_path / "gui").resolve()), "steps": 5, "format": "bmp"}
    )
    assert (reply["result"]["files"], reply["result"]["uncertainty_pct"]) == (5, 15.0)
    assert reply["result"]["factors"] == [0.85, 0.925, 1.0, 1.075, 1.15]
    assert len(list((tmp_path / "gui").glob("*.bmp"))) == 5
    assert rpc("sweep.export", {"sha256": gray, "dest": str((tmp_path / "gui2").resolve()), "format": "jp2"})["error"]
    session.close()
