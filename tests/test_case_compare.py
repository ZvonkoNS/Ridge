"""Reference images and comparison sheets (PRD FR-52): view only, equal scale, logged, never guessed."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from ridge.case import compare
from ridge.case.compare import build_sheet, export_sheet, file_ppi
from ridge.case.crypto import sha256_hex
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import OpenCase, open_case
from ridge.case.verify import verify_case
from ridge.errors import ExtractionError, IntegrityError, OutputExistsError, ParameterError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


def reference_png(path: Path, *, dpi: tuple[float, float] | None, size: tuple[int, int] = (400, 300)) -> Path:
    """A synthetic grey ridge-like image standing in for an AFIS candidate."""
    w, h = size
    stripes = (127 + 100 * np.sin(np.arange(w) / 3.0)).astype(np.uint8)
    image = Image.fromarray(np.tile(stripes, (h, 1)))
    image.save(path, format="PNG", **({"dpi": dpi} if dpi else {}))
    return path


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


@pytest.fixture
def export_sha(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> str:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo_file(tmp_path / "in"))
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams())
    return next(o.sha256 for o in outcome.outputs if o.role == "export")


def import_reference(case_dir: Path, keystore: MemoryKeyStore, path: Path, source: str = "NAFIS candidate 3") -> str:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        return case.import_reference(path, source).sha256


def test_reference_is_hashed_logged_and_never_processed(
    case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path
) -> None:
    path = reference_png(tmp_path / "candidate.png", dpi=(500, 500))
    sha = import_reference(case_dir, keystore, path)
    assert sha == sha256_hex(path.read_bytes())
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        item = case.item(sha)
        assert (item.role, item.source, item.label) == ("reference", "NAFIS candidate 3", "candidate.png")
        entry = next(e for e in case.entries if e["action"] == "reference.import")
        assert entry["source"] == "NAFIS candidate 3"
        with pytest.raises(ExtractionError, match="evidence items only"):
            run_extraction_job(case, sha, signer, JobParams())
        with pytest.raises(ParameterError):
            case.store_artefact(b"x", role="reference", label="x", job_id="j")
        case.import_reference(path, "again")
        assert case.entries[-1]["result"] == "duplicate"
        assert verify_case(case, case_dir.parent).ok


def test_sheet_puts_both_at_equal_scale(
    case_dir: Path, keystore: MemoryKeyStore, export_sha: str, tmp_path: Path
) -> None:
    ref = import_reference(case_dir, keystore, reference_png(tmp_path / "c.png", dpi=(1000, 1000)))
    dest = tmp_path / "sheet.png"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        export_w = Image.open(io.BytesIO(case.read(export_sha, log=False))).size[0]
        sheet = export_sheet(case, export_sha[:12], ref[:12], dest)
        entry = case.entries[-1]
    assert (sheet.reference_ppi, sheet.reference_ppi_source, sheet.ppi) == (1000.0, "file", 500.0)
    assert sha256_hex(dest.read_bytes()) == sheet.sha256
    with Image.open(dest) as im:
        assert im.mode == "L"
        assert im.info["dpi"][0] == pytest.approx(500, abs=0.01)
        width = im.size[0]
    assert width >= export_w + 200  # the 1000 ppi, 400 px wide reference is 200 px wide at 500 ppi
    assert entry["action"] == "comparison.export"
    assert (entry["export_sha256"], entry["reference_sha256"], entry["sha256"]) == (export_sha, ref, sheet.sha256)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        reads = [e["action"] for e in case.entries if e.get("sha256") in (export_sha, ref)]
    assert {"export.read", "reference.read"} <= set(reads)


def test_resolution_is_never_guessed(case_dir: Path, keystore: MemoryKeyStore, export_sha: str, tmp_path: Path) -> None:
    bare = import_reference(case_dir, keystore, reference_png(tmp_path / "bare.png", dpi=None), "x" * 120)
    screen = import_reference(case_dir, keystore, reference_png(tmp_path / "screen.png", dpi=(72, 72), size=(50, 50)))
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        with pytest.raises(ParameterError, match="declares no resolution"):
            build_sheet(case, export_sha, bare)
        assert build_sheet(case, export_sha, bare, reference_ppi=500).reference_ppi_source == "examiner"
        with pytest.raises(ParameterError, match="not a fingerprint resolution"):
            build_sheet(case, export_sha, screen)
        for kwargs in ({"reference_ppi": 10.0}, {"ppi": 5000.0}):
            with pytest.raises(ParameterError, match="not a fingerprint resolution"):
                build_sheet(case, export_sha, bare, **kwargs)


def test_roles_are_checked(case_dir: Path, keystore: MemoryKeyStore, export_sha: str, tmp_path: Path) -> None:
    ref = import_reference(case_dir, keystore, reference_png(tmp_path / "c.png", dpi=(500, 500)))
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = next(i.sha256 for i in case.items() if i.role == "evidence")
        with pytest.raises(ParameterError, match="not a comparison export"):
            build_sheet(case, ref, ref)
        with pytest.raises(ParameterError, match="not an imported reference"):
            build_sheet(case, export_sha, evidence)


def test_no_silent_overwrite(case_dir: Path, keystore: MemoryKeyStore, export_sha: str, tmp_path: Path) -> None:
    ref = import_reference(case_dir, keystore, reference_png(tmp_path / "c.png", dpi=(500, 500)))
    dest = tmp_path / "sheet.png"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        export_sheet(case, export_sha, ref, dest)
        with pytest.raises(OutputExistsError):
            export_sheet(case, export_sha, ref, dest)
        export_sheet(case, export_sha, ref, dest, overwrite=True)


def test_size_limits_and_lost_metadata(
    case_dir: Path, keystore: MemoryKeyStore, export_sha: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    at_500 = import_reference(case_dir, keystore, reference_png(tmp_path / "a.png", dpi=(500, 500)))
    at_1000 = import_reference(case_dir, keystore, reference_png(tmp_path / "b.png", dpi=(1000, 1000)))
    case: OpenCase
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        monkeypatch.setattr(compare, "MAX_SHEET_PIXELS", 1000)
        for ref in (at_1000, at_500):  # refused while resampling, and when composing
            with pytest.raises(ParameterError, match="too large"):
                build_sheet(case, export_sha, ref)
        monkeypatch.setattr(compare, "file_ppi", lambda data: None)
        with pytest.raises(IntegrityError, match="lost its resolution"):
            build_sheet(case, export_sha, at_500)


def test_file_ppi_needs_one_resolution(tmp_path: Path) -> None:
    assert file_ppi(reference_png(tmp_path / "a.png", dpi=(500, 500)).read_bytes()) == pytest.approx(500, abs=0.01)
    assert file_ppi(reference_png(tmp_path / "b.png", dpi=(500, 1000)).read_bytes()) is None
    assert file_ppi(reference_png(tmp_path / "c.png", dpi=None).read_bytes()) is None


def test_unlogged_sheet_is_removed(
    case_dir: Path, keystore: MemoryKeyStore, export_sha: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = import_reference(case_dir, keystore, reference_png(tmp_path / "c.png", dpi=(500, 500)))
    dest = tmp_path / "sheet.png"
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        real = case.custody.append

        def refuse_export(action: str, **fields: Any) -> Any:
            if action == "comparison.export":
                raise OSError("log unavailable")
            return real(action, **fields)

        monkeypatch.setattr(case.custody, "append", refuse_export)
        with pytest.raises(OSError, match="log unavailable"):
            export_sheet(case, export_sha, ref, dest)
    assert not dest.exists()  # no plaintext sheet without its custody entry
