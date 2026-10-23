"""``tools/decoder_evidence.py``: it hashes what a job stores, and `compare` only reports real evidence."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.store import open_case
from ridge.image_io import ReadLimits, decode_image
from ridge.pipeline import extract_fingerprint
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME

ROOT = Path(__file__).resolve().parents[1]


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("decoder_evidence", ROOT / "tools" / "decoder_evidence.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _tool()


def test_the_export_hash_is_the_export_a_default_job_stores(tmp_path: Path) -> None:
    keystore, store = MemoryKeyStore(), tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(store, keystore)
    photo = write_png(tmp_path / "finger.png", CASES_BY_NAME["whorl_default"].photo())
    signer = unlock_identity(store, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        item = case.import_evidence(photo)
        outcome = run_extraction_job(case, item.sha256, signer, JobParams())
    stored = next(o for o in outcome.outputs if o.role == "export")
    result = extract_fingerprint(decode_image(photo.read_bytes(), ReadLimits()))
    assert TOOL._export(result) == {"export_png": stored.sha256}


def _manifest(path: Path, pillow: str, files: dict[str, Any]) -> Path:
    path.write_bytes(json.dumps({"environment": {"pillow": pillow, "python": "3.13.5"}, "files": files}).encode())
    return path


def test_compare_needs_two_versions_and_reports_every_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"a.jpg": {"decoded": "1", "print": "2"}}
    old = _manifest(tmp_path / "old.json", "12.3.0", files)
    assert TOOL.compare(old, _manifest(tmp_path / "same.json", "12.3.0", files)) == 2
    assert "the manifests do not compare two versions" in capsys.readouterr().out
    assert TOOL.compare(old, _manifest(tmp_path / "new.json", "13.0.0", files)) == 0
    assert "1 of 1 inputs give identical results" in capsys.readouterr().out
    changed = {"a.jpg": {"decoded": "1", "print": "3"}}
    assert TOOL.compare(old, _manifest(tmp_path / "changed.json", "13.0.0", changed)) == 1
    out = capsys.readouterr().out
    assert "environment pillow: 12.3.0 -> 13.0.0" in out
    assert "DIFFERENT a.jpg" in out
