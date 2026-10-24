"""Comparison export and NFIQ 2 inside case jobs (PRD FR-30 to FR-34)."""

from __future__ import annotations

import getpass
import io
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from PIL import Image

from ridge import extract_fingerprint
from ridge.case import cli_common, jobs
from ridge.case.cli import main
from ridge.case.export_step import ExportOptions
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobOutcome, JobParams, run_extraction_job
from ridge.case.store import open_case
from ridge.errors import ParameterError
from ridge.export import ReferenceKind, make_comparison_export, scale_from_ridge_period
from ridge.image_io import load_image
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def run_job(
    case_dir: Path, keystore: MemoryKeyStore, photo: Path, **kwargs: Any
) -> tuple[JobOutcome, dict[str, bytes]]:
    nfiq2 = kwargs.pop("nfiq2_command", None)
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams(**kwargs), nfiq2_command=nfiq2)
        blobs = {o.role: case.read(o.sha256, log=False) for o in outcome.outputs}
    return outcome, blobs


def test_export_is_stored_recorded_and_matches_the_library(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path
) -> None:
    photo = photo_file(tmp_path / "in")
    outcome, blobs = run_job(case_dir, keystore, photo)
    export = outcome.report["export"]
    assert export["produced"] is True
    assert export["transforms"] == ["polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ridge-period"]
    assert export["scale"]["method"] == "ridge-period"
    assert export["scale"]["assumed_ridge_period_mm"] == 0.47
    assert export["scale"]["uncertainty_pct"] == 15.0
    assert outcome.report["quality"] == {
        "nfiq2": {"computed": False, "reason": "NFIQ 2 is not configured", "image": "export-gray"}
    }

    with Image.open(io.BytesIO(blobs["export"])) as im:
        assert im.mode == "L"
        assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)
        stored = np.asarray(im)
    direct = extract_fingerprint(load_image(photo))
    expected = make_comparison_export(direct, scale_from_ridge_period(direct.period)).image
    assert np.array_equal(stored, expected)  # the case job produces exactly the library's export
    assert np.median(stored) > 127  # dark ridges on a light background


def test_ruler_scale_and_unusable_scale(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in")
    outcome, _ = run_job(case_dir, keystore, photo, export=ExportOptions(ruler=(10.0, 10.0, 110.0, 10.0, 5.0)))
    scale = outcome.report["export"]["scale"]
    assert scale["method"] == "ruler"
    assert scale["px_per_mm"] == pytest.approx(20.0)
    assert outcome.report["export"]["transforms"][-1] == "scale:500ppi:ruler"

    other = photo_file(tmp_path / "in2", "arch_default", "arch.png")
    outcome, blobs = run_job(case_dir, keystore, other, export=ExportOptions(ruler=(0.0, 0.0, 1.0, 0.0, 1000.0)))
    assert outcome.report["export"]["produced"] is False  # recorded, the job still succeeds
    assert "MP" in outcome.report["export"]["reason"]
    assert "export" not in blobs


def test_export_can_be_switched_off(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    outcome, blobs = run_job(case_dir, keystore, photo_file(tmp_path / "in"), export=ExportOptions(enabled=False))
    assert outcome.report["export"] is None
    assert set(blobs) == {"print"}


def fake_nfiq2(folder: Path, output: str) -> list[str]:
    script = folder / "fake_nfiq2.py"
    script.write_text(f"import sys\nprint({output!r})\n", encoding="utf-8")
    return [sys.executable, str(script)]


def test_nfiq2_score_is_recorded_as_indicative(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    command = fake_nfiq2(tmp_path, "42")
    outcome, _ = run_job(case_dir, keystore, photo_file(tmp_path / "in"), nfiq2_command=command)
    nfiq2 = outcome.report["quality"]["nfiq2"]
    assert nfiq2["computed"] is True
    assert nfiq2["score"] == 42
    assert "indicative" in nfiq2["label"]
    assert not (case_dir / "work").exists()  # the plaintext copy for the tool is gone


def test_missing_nfiq2_is_not_a_failure(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    missing = str((tmp_path / "no" / "nfiq2.exe").resolve())
    outcome, _ = run_job(case_dir, keystore, photo_file(tmp_path / "in"), nfiq2_command=[missing])
    nfiq2 = outcome.report["quality"]["nfiq2"]
    assert nfiq2["computed"] is False
    assert "not installed" in nfiq2["reason"]


@pytest.fixture
def cli_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Path:
    shared = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: shared)
    monkeypatch.setattr(cli_common, "KDF_PARAMS", FAST_KDF)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    store = tmp_path / "store"
    assert main(["identity", "init", "--store", str(store)]) == 0
    args = ["init", "--store", str(store), "--reference", "KT", "--legal-basis", "b", "--retention", "2099-01-01"]
    assert main(args) == 0
    case_dir = Path(capsys.readouterr().out.strip().splitlines()[-1].split("case created: ")[1])
    assert main(["import", str(case_dir), str(photo_file(tmp_path / "in"))]) == 0
    capsys.readouterr()
    return case_dir


def test_cli_extract_with_ruler_and_nfiq2(cli_case: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with open_case(cli_case, PASSPHRASE, cli_common.KEYSTORE_FACTORY()) as case:
        sha = case.items()[0].sha256
    command = fake_nfiq2(tmp_path, "37")
    args = ["extract", str(cli_case), "--evidence", sha, "--ruler", "0", "0", "200", "0", "10"]
    args += ["--nfiq2", command[0], "--nfiq2-arg", command[1]]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "export 500 ppi (scale: ruler" in out
    assert "NFIQ 2 37 (indicative)" in out


def test_cli_ruler_needs_a_single_photo(cli_case: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extract", str(cli_case), "--all", "--ruler", "0", "0", "200", "0", "10"]) == 1
    assert "exactly one --evidence" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("kwargs", "nfiq2"),
    [
        ({"export": ExportOptions(target_ppi=0.0)}, None),
        ({"export": ExportOptions(ruler=(5.0, 5.0, 5.0, 5.0, 10.0))}, None),  # coincident ruler points
        ({}, ["relative/nfiq2.exe"]),
    ],
)
def test_invalid_settings_are_refused_before_the_job_starts(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, kwargs: dict[str, Any], nfiq2: list[str] | None
) -> None:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        before = len(case.entries)
        with pytest.raises(ParameterError):
            run_extraction_job(case, evidence.sha256, signer, JobParams(**kwargs), nfiq2_command=nfiq2)
        assert len(case.entries) == before  # no job.start, nothing stored
        assert [i.role for i in case.items()] == ["evidence"]


def test_any_failure_after_start_closes_the_job(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(jobs, "export_and_score", broken)
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        with pytest.raises(RuntimeError):
            run_extraction_job(case, evidence.sha256, signer, JobParams())
        last = case.entries[-1]
        assert (last["action"], last["result"]) == ("job.end", "failed")
        assert last["error"] == "internal error (RuntimeError)"


def test_nfiq2_is_skipped_unless_the_export_is_500_ppi(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path
) -> None:
    command = fake_nfiq2(tmp_path, "42")
    outcome, _ = run_job(
        case_dir, keystore, photo_file(tmp_path / "in"), export=ExportOptions(target_ppi=1000.0), nfiq2_command=command
    )
    nfiq2 = outcome.report["quality"]["nfiq2"]
    assert nfiq2["computed"] is False
    assert "500 ppi" in nfiq2["reason"]


def hashing_nfiq2(folder: Path, seen: Path, output: str) -> list[str]:
    """A fake NFIQ 2 that records the SHA-256 of the image it was given (its last argument)."""
    script = folder / "hashing_nfiq2.py"
    script.write_text(
        "import hashlib, sys\nfrom pathlib import Path\n"
        "Path(sys.argv[1]).write_text(hashlib.sha256(Path(sys.argv[-1]).read_bytes()).hexdigest(), encoding='utf-8')\n"
        f"print({output!r})\n",
        encoding="utf-8",
    )
    return [sys.executable, str(script), str(seen)]


def test_grayscale_export_is_stored_and_scored(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in")
    seen = tmp_path / "seen.txt"
    outcome, blobs = run_job(case_dir, keystore, photo, nfiq2_command=hashing_nfiq2(tmp_path, seen, "61"))
    gray = outcome.report["export"]["grayscale"]
    assert gray["transforms"] == [
        "tone:grayscale",
        "polarity:dark-ridges",
        "mirror:horizontal",
        "scale:500ppi:ridge-period",
    ]
    item = next(o for o in outcome.outputs if o.role == "export-gray")
    assert (item.sha256, item.label) == (gray["sha256"], "finger_comparison_gray_500ppi.png")
    assert [o.role for o in outcome.outputs] == ["print", "export", "export-gray"]
    with Image.open(io.BytesIO(blobs["export-gray"])) as im:
        assert im.mode == "L"
        assert im.info["dpi"] == pytest.approx((500, 500), abs=0.1)
        stored = np.asarray(im)
    with Image.open(io.BytesIO(blobs["export"])) as im:
        assert stored.shape == np.asarray(im).shape  # the same geometry as the binary export
    assert len(np.unique(stored)) > 2
    direct = extract_fingerprint(load_image(photo))
    expected = make_comparison_export(direct, scale_from_ridge_period(direct.period), tone="grayscale").image
    assert np.array_equal(stored, expected)
    nfiq2 = outcome.report["quality"]["nfiq2"]
    assert (nfiq2["computed"], nfiq2["score"], nfiq2["image"]) == (True, 61, "export-gray")
    assert seen.read_text(encoding="utf-8").strip() == item.sha256  # the tool scored the grayscale export


def test_card_reference_scale_and_the_no_reference_notice(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path
) -> None:
    photo = photo_file(tmp_path / "in")
    card = ExportOptions(ruler=(10.0, 10.0, 352.4, 10.0, 85.6), reference="id1-long")  # 342.4 px across the card
    outcome, _ = run_job(case_dir, keystore, photo, export=card)
    scale = outcome.report["export"]["scale"]
    assert (scale["method"], scale["reference"]) == ("card", "ISO/IEC 7810 ID-1 card, long edge (85.60 mm)")
    assert scale["px_per_mm"] == pytest.approx(4.0)
    assert "notice" not in scale
    assert outcome.report["parameters"]["export"]["reference"] == "id1-long"
    assert outcome.report["export"]["transforms"][-1] == "scale:500ppi:card"

    estimated, _ = run_job(case_dir, keystore, photo_file(tmp_path / "in2", "arch_default", "arch.png"))
    scale = estimated.report["export"]["scale"]
    assert scale["method"] == "ridge-period"
    assert "ruler or an ISO/IEC 7810 ID-1 card" in scale["notice"]
    assert "Otherwise proceed" in scale["notice"]
    assert "reference" not in scale


@pytest.mark.parametrize(
    "export",
    [
        ExportOptions(ruler=(0.0, 0.0, 856.0, 0.0, 80.0), reference="id1-long"),  # not the standard edge length
        ExportOptions(reference="id1-short"),  # a card kind without its points
        ExportOptions(ruler=(0.0, 0.0, 856.0, 0.0, 85.6), reference=cast(ReferenceKind, "coin")),
    ],
)
def test_bad_scale_references_are_refused_before_the_job_starts(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path, export: ExportOptions
) -> None:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        before = len(case.entries)
        with pytest.raises(ParameterError):
            run_extraction_job(case, evidence.sha256, signer, JobParams(export=export))
        assert len(case.entries) == before  # nothing started, nothing logged


def test_cli_card_reference_and_scale_notice(cli_case: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with open_case(cli_case, PASSPHRASE, cli_common.KEYSTORE_FACTORY()) as case:
        sha = case.items()[0].sha256
    card = ["extract", str(cli_case), "--evidence", sha, "--card", "long", "0", "0", "342.4", "0"]
    assert main(card) == 0
    out = capsys.readouterr().out
    assert "export 500 ppi (scale: card" in out
    assert "scale notice" not in out
    assert main(["extract", str(cli_case), "--evidence", sha]) == 0
    assert "scale notice: No scale reference was given" in capsys.readouterr().out
    assert main(["extract", str(cli_case), "--evidence", sha, "--card", "wide", "0", "0", "342.4", "0"]) == 1
    assert "long or short" in capsys.readouterr().err
    assert main([*card, "--ruler", "0", "0", "1", "0", "1"]) == 1
    assert "not both" in capsys.readouterr().err


def test_an_enlarged_export_carries_a_resolution_note(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    photo = photo_file(tmp_path / "in")
    outcome, _ = run_job(case_dir, keystore, photo, export=ExportOptions(target_ppi=1000.0))
    export = outcome.report["export"]
    assert export["factor"] > 1.05
    assert "enlarged" in export["resolution_note"]
    assert "1000 ppi" in export["resolution_note"]
    plain, _ = run_job(case_dir, keystore, photo_file(tmp_path / "in2", "arch_default", "arch.png"))
    assert plain.report["export"]["factor"] < 1.0
    assert "resolution_note" not in plain.report["export"]


def test_cli_prints_the_resolution_note(cli_case: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with open_case(cli_case, PASSPHRASE, cli_common.KEYSTORE_FACTORY()) as case:
        sha = case.items()[0].sha256
    assert main(["extract", str(cli_case), "--evidence", sha, "--ppi", "1000"]) == 0
    assert "resolution note: The export was enlarged" in capsys.readouterr().out
