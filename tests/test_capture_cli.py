"""``ridge-case check-photo`` and the sidecar's ``photo.check`` / ``evidence.check`` (FR-54), synthetic images only."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import pytest

from ridge.capture import NOTICE, SCHEMA
from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity
from ridge.case.store import open_case
from ridge.image_io import encode_image
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.synthetic import finger_photo, whorl_pattern


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


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "in" / "finger.png"
    path.parent.mkdir()
    path.write_bytes(encode_image(finger_photo(whorl_pattern(480, 360, 9.0)), ".png"))
    return path


def test_the_cli_checks_a_file_without_a_case(photo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check-photo", str(photo)]) == 0
    out = capsys.readouterr().out
    assert "No reason to photograph the finger again was found." in out
    assert "[ok] The finger fills 40 % of the frame." in out
    assert "[note] Ridge cannot see whether a ruler" in out
    assert NOTICE in out
    assert main(["check-photo", str(photo), "--json"]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["schema"] == SCHEMA
    assert record["verdict"] == "ok"
    assert record["finger_located"] is True


def test_the_cli_checks_a_stored_photo_with_a_logged_read(
    case_dir: Path, keystore: MemoryKeyStore, photo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        sha = case.import_evidence(photo).sha256
        reads_before = sum(e["action"] == "evidence.read" for e in case.entries)
    assert main(["check-photo", "--case", str(case_dir), sha[:12]]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"evidence {sha}  finger.png")
    assert "capture check" in out
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        assert sum(e["action"] == "evidence.read" for e in case.entries) == reads_before + 1
        outcome_sha = None
        for item in case.items():
            if item.role == "evidence":
                outcome_sha = item.sha256
        assert outcome_sha == sha
    assert main(["check-photo", "--case", str(case_dir), "0" * 64]) != 0  # no such item


def test_the_sidecar_checks_before_and_after_import(case_dir: Path, keystore: MemoryKeyStore, photo: Path) -> None:
    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    before = rpc("photo.check", {"path": str(photo.resolve())})["result"]  # no case is unlocked
    assert before["schema"] == SCHEMA
    assert before["verdict"] == "ok"
    assert rpc("photo.check", {"path": "finger.png"})["error"]["code"] == -32000  # relative paths are refused
    assert rpc("photo.check", {"path": str(photo), "extra": 1})["error"]["code"] == -32602
    assert rpc("evidence.check", {"sha256": "0" * 64})["error"]["code"] == -32000  # no case yet
    with open_case(case_dir, PASSPHRASE, keystore) as case:  # imported before the sidecar holds the case
        sha = case.import_evidence(photo).sha256
    store = case_dir.parent
    rpc("session.unlock", {"store": str(store.resolve()), "case_id": case_dir.name, "passphrase": PASSPHRASE})
    after = rpc("evidence.check", {"sha256": sha})["result"]
    assert after["role"] == "evidence"
    assert after["label"] == "finger.png"
    assert after["sha256"] == sha
    assert after["verdict"] == "ok"
    assert {f["id"] for f in after["findings"]} == {f["id"] for f in before["findings"]}
    assert rpc("evidence.check", {"sha256": 5})["error"]["code"] == -32602
    session.close()
