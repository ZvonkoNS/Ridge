"""``ridge-case limits`` and limit warnings in ``ridge-case extract`` (PRD §12 item 8)."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.limits import FILE, SCHEMA
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, future, photo_file


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> tuple[Path, Path]:
    shared = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: shared)
    monkeypatch.setattr(cli_common, "KDF_PARAMS", FAST_KDF)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    root = tmp_path / "store"
    assert main(["identity", "init", "--store", str(root)]) == 0
    init = ["init", "--store", str(root), "--reference", "KT-9", "--legal-basis", "synthetic"]
    assert main([*init, "--retention", future().isoformat()]) == 0
    case = Path(capsys.readouterr().out.strip().splitlines()[-1].split("case created: ")[1])
    return root, case


def write_limits(path: Path, **fields: object) -> None:
    path.write_text(json.dumps({"schema": SCHEMA, "source": "VR-2027-01", **fields}), encoding="utf-8")


def test_limits_are_shown_and_checked(
    store: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = store
    assert main(["limits", "--store", str(root)]) == 0
    assert "no limits of use configured" in capsys.readouterr().out
    candidate = tmp_path / "candidate.json"
    write_limits(candidate, min_ridge_period_px=7, require_ruler=True)
    assert main(["limits", "--check", str(candidate)]) == 0
    shown = capsys.readouterr().out
    assert "limits of use from VR-2027-01, sha256 " in shown
    assert "min_ridge_period_px: 7.0" in shown
    write_limits(candidate, unknown=1)
    assert main(["limits", "--check", str(candidate)]) == 1  # refused (RidgeError)


def test_extract_prints_deviations_and_a_broken_file_stops_jobs(
    store: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, case = store
    assert main(["import", str(case), str(photo_file(tmp_path / "in"))]) == 0
    write_limits(root / FILE, min_ridge_period_px=500)
    capsys.readouterr()
    assert main(["extract", str(case), "--all"]) == 0
    assert "outside the limits of use: ridge period" in capsys.readouterr().out
    (root / FILE).write_text("{", encoding="utf-8")
    assert main(["extract", str(case), "--all"]) == 1  # refused before any job starts
    assert "limits of use" in capsys.readouterr().err
