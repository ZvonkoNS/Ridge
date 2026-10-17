"""``ridge-case`` end to end with synthetic data, an in-memory keystore and scripted passphrases."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

import ridge.case.cli as case_cli
from ridge.case.cli import main
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, future, photo_file


@pytest.fixture
def keystore(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyStore:
    shared = MemoryKeyStore()
    monkeypatch.setattr(case_cli, "KEYSTORE_FACTORY", lambda: shared)
    monkeypatch.setattr(case_cli, "KDF_PARAMS", FAST_KDF)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    return shared


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]) -> Path:
    store = tmp_path / "store"
    assert main(["identity", "init", "--store", str(store)]) == 0
    retention = future().isoformat()
    args = [
        "init",
        "--store",
        str(store),
        "--reference",
        "KT-1",
        "--legal-basis",
        "synthetic",
        "--retention",
        retention,
    ]
    assert main(args) == 0
    out = capsys.readouterr().out
    return Path(out.strip().splitlines()[-1].split("case created: ")[1])


def test_full_workflow(case_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    photo = photo_file(tmp_path / "in")
    assert main(["import", str(case_dir), str(photo)]) == 0
    sha = capsys.readouterr().out.split("evidence ")[1].split()[0]

    assert main(["extract", str(case_dir), "--all", "--debug"]) == 0
    assert "ridge spacing 8.8px" in capsys.readouterr().out

    assert main(["list", str(case_dir)]) == 0
    listing = capsys.readouterr().out
    assert "reference KT-1" in listing
    print_sha = next(line.split()[1] for line in listing.splitlines() if line.startswith("print"))

    dest = tmp_path / "export.png"
    assert main(["export", str(case_dir), print_sha, "--to", str(dest)]) == 0
    assert dest.is_file()
    assert main(["export", str(case_dir), print_sha, "--to", str(dest)]) == 1  # no silent overwrite
    capsys.readouterr()

    assert main(["verify", str(case_dir)]) == 0
    assert "verification passed" in capsys.readouterr().out

    assert main(["log", str(case_dir)]) == 0
    actions = [json.loads(line)["action"] for line in capsys.readouterr().out.splitlines()]
    assert actions[:2] == ["case.create", "evidence.import"]
    assert {"job.start", "report.sign", "job.end", "chain.sign", "artefact.export", "case.verify"} <= set(actions)

    record = tmp_path / "record.json"
    assert main(["log", str(case_dir), "--to", str(record)]) == 0
    assert "processing record with" in capsys.readouterr().out
    assert main(["log", str(case_dir), "--to", str(record)]) == 1  # never overwritten silently
    assert main(["check-log", str(record)]) == 0
    out = capsys.readouterr().out
    assert "chain intact" in out
    assert "WARNING" not in out
    key_id = out.split("signed by key ")[1].split(":")[0]
    assert main(["check-log", str(record), "--key-id", key_id]) == 0
    assert "expected key" in capsys.readouterr().out
    record.write_text(record.read_text(encoding="utf-8").replace("case.create", "case.CREATE"), encoding="utf-8")
    assert main(["check-log", str(record)]) == 1
    assert sha  # imported evidence id was printed


def test_hold_and_dispose(case_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    case_id = case_dir.name
    assert main(["hold", str(case_dir), "--on", "--reason", "synthetic hold"]) == 0
    dispose = ["dispose", str(case_dir), "--confirm", case_id, "--reason", "proceedings-closed", "--before-retention"]
    assert main(dispose) == 1
    assert "legal hold" in capsys.readouterr().err
    assert main(["hold", str(case_dir), "--off", "--reason", "released"]) == 0
    assert main(dispose) == 0
    assert not case_dir.exists()


def test_tampering_fails_verification(case_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["import", str(case_dir), str(photo_file(tmp_path / "in"))]) == 0
    blob = next((case_dir / "evidence").iterdir())
    data = bytearray(blob.read_bytes())
    data[-1] ^= 1
    blob.write_bytes(bytes(data))
    assert main(["verify", str(case_dir)]) == 1
    captured = capsys.readouterr()
    assert "verification FAILED" in captured.out
    assert "PROBLEM: evidence" in captured.err


def test_wrong_passphrase(case_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "not the right passphrase")
    assert main(["list", str(case_dir)]) == 1
    assert "wrong passphrase" in capsys.readouterr().err


def test_identity_passphrase_must_repeat(
    tmp_path: Path, keystore: MemoryKeyStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = iter([PASSPHRASE, PASSPHRASE + "typo"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(answers))
    assert main(["identity", "init", "--store", str(tmp_path / "s")]) == 1
    assert "do not match" in capsys.readouterr().err


def test_init_needs_an_identity(tmp_path: Path, keystore: MemoryKeyStore, capsys: pytest.CaptureFixture[str]) -> None:
    args = [
        "init",
        "--store",
        str(tmp_path / "s"),
        "--reference",
        "KT",
        "--legal-basis",
        "b",
        "--retention",
        "2099-01-01",
    ]
    assert main(args) == 1
    assert "identity init" in capsys.readouterr().err


def test_init_refuses_a_passphrase_that_does_not_unlock_the_identity(
    case_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = case_dir.parent
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "a different long passphrase")
    args = ["init", "--store", str(store), "--reference", "KT-2", "--legal-basis", "b", "--retention", "2099-01-01"]
    assert main(args) == 1
    assert "wrong passphrase" in capsys.readouterr().err
    assert sorted(p.name for p in store.iterdir()) == sorted(["identity.json", case_dir.name])  # no new case


def test_extract_needs_a_selection(case_dir: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["extract", str(case_dir)])
    assert excinfo.value.code == 2


def test_internal_errors_exit_3(
    case_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(case_cli, "open_case", boom)
    assert main(["list", str(case_dir)]) == 3
    assert "internal error (RuntimeError)" in capsys.readouterr().err
    assert main(["--verbose", "list", str(case_dir)]) == 3
    assert "Traceback" in capsys.readouterr().err


def test_jobs_and_reports(case_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["jobs", str(case_dir)]) == 0
    assert capsys.readouterr().out.strip() == "no jobs"
    assert main(["import", str(case_dir), str(photo_file(tmp_path / "in"))]) == 0
    assert main(["extract", str(case_dir), "--all"]) == 0
    capsys.readouterr()

    assert main(["jobs", str(case_dir)]) == 0
    listing = capsys.readouterr().out
    assert "ok      evidence" in listing
    assert "signed report" in listing
    job_id = listing.split()[0]

    assert main(["report", str(case_dir), job_id[:8]]) == 0
    assert f"Job report {job_id}   signature verified" in capsys.readouterr().out
    assert main(["report", str(case_dir), job_id, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["job_id"] == job_id
    assert main(["report", str(case_dir), "../escape"]) == 1
    capsys.readouterr()

    dest = tmp_path / "report.json"
    assert main(["report", str(case_dir), job_id, "--to", str(dest)]) == 0
    assert "exported" in capsys.readouterr().out
    assert main(["report", str(case_dir), job_id, "--to", str(dest)]) == 1  # no silent overwrite
    assert main(["report", str(case_dir), job_id, "--to", str(dest), "--overwrite"]) == 0
    capsys.readouterr()

    assert main(["check-report", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "signature valid" in out
    assert "confirm it is the examiner's key" in out
    key_id = out.split("signed by key ")[1].split(":")[0]
    assert main(["check-report", str(dest), "--sig", f"{dest}.sig", "--key-id", key_id]) == 0
    assert f"signed by the expected key {key_id}" in capsys.readouterr().out
    dest.write_bytes(dest.read_bytes().replace(job_id.encode(), job_id[::-1].encode()))  # still canonical
    assert main(["check-report", str(dest)]) == 1
    assert "ridge-case:" in capsys.readouterr().err


def test_reference_and_comparison_sheet(case_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["import", str(case_dir), str(photo_file(tmp_path / "in"))]) == 0
    assert main(["extract", str(case_dir), "--all"]) == 0
    capsys.readouterr()
    candidate = tmp_path / "candidate.png"
    Image.fromarray(np.full((100, 80), 128, np.uint8)).save(candidate, dpi=(500, 500))
    assert main(["import-reference", str(case_dir), str(candidate), "--source", "NAFIS candidate 1"]) == 0
    reference = capsys.readouterr().out.split("reference ")[1].split()[0]
    assert main(["list", str(case_dir)]) == 0
    listing = capsys.readouterr().out.splitlines()
    export = next(line.split()[1] for line in listing if line.startswith("export"))
    assert any(line.startswith("reference") for line in listing)
    sheet = tmp_path / "sheet.png"
    assert main(["compare", str(case_dir), export, reference, "--to", str(sheet)]) == 0
    assert "view aid only, no matching" in capsys.readouterr().out
    assert main(["compare", str(case_dir), export, reference, "--to", str(sheet)]) == 1
    assert main(["compare", str(case_dir), export, reference, "--to", str(sheet), "--overwrite", "--ppi", "1000"]) == 0


def test_reproduce(
    case_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from ridge.case import jobs  # noqa: PLC0415
    from ridge.pipeline import extract_fingerprint  # noqa: PLC0415

    assert main(["import", str(case_dir), str(photo_file(tmp_path / "in"))]) == 0
    assert main(["extract", str(case_dir), "--all"]) == 0
    capsys.readouterr()
    assert main(["jobs", str(case_dir)]) == 0
    job_id = capsys.readouterr().out.split()[0]
    assert main(["reproduce", str(case_dir), job_id[:8]]) == 0
    assert "identical outputs" in capsys.readouterr().out

    env = jobs.environment()

    def drifted(*args: Any, **kwargs: Any) -> Any:  # stands in for another platform's floating point
        result = extract_fingerprint(*args, **kwargs)
        result.image[0, 0] = 255 - int(result.image[0, 0])
        return result

    monkeypatch.setattr(jobs, "extract_fingerprint", drifted)
    monkeypatch.setattr(jobs, "environment", lambda: {**env, "machine": "other\x1b[2J"})
    assert main(["reproduce", str(case_dir), job_id]) == 1
    captured = capsys.readouterr()
    assert "NOT reproduced" in captured.out
    assert "environment changed: machine" in captured.out
    assert "\x1b" not in captured.out
    assert "differs: print:" in captured.err
