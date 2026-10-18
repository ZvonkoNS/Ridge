"""Verifying every case of a store with one passphrase (FR-24)."""

from __future__ import annotations

import getpass
import json
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity
from ridge.case.store import open_case
from ridge.case.store_verify import verify_store
from ridge.errors import KeyCustodyError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, MemoryKeyStore, list[Path]]:
    keystore = MemoryKeyStore()
    root = tmp_path / "store"
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    cases = [new_case(root, keystore, reference=f"KT-2026-{n}") for n in (1, 2)]
    with open_case(cases[1], PASSPHRASE, keystore) as case:
        case.import_evidence(photo_file(tmp_path / "in"))
    return root, keystore, cases


def test_every_case_is_verified_and_a_damaged_one_is_named(
    store: tuple[Path, MemoryKeyStore, list[Path]], tmp_path: Path
) -> None:
    root, keystore, cases = store
    results = {r.case_id: r for r in verify_store(root, PASSPHRASE, keystore)}
    assert all(r.ok and r.checked for r in results.values())
    assert {r.reference for r in results.values()} == {"KT-2026-1", "KT-2026-2"}
    blob = next((cases[1] / "evidence").iterdir())
    data = bytearray(blob.read_bytes())
    data[-1] ^= 1
    blob.write_bytes(bytes(data))
    damaged = {r.case_id: r for r in verify_store(root, PASSPHRASE, keystore)}[cases[1].name]
    assert (damaged.checked, damaged.ok) == (True, False)
    assert damaged.problems
    with open_case(cases[0], PASSPHRASE, keystore) as case:
        assert any(e["action"] == "case.verify" for e in case.entries)  # each verification is logged


def test_a_wrong_passphrase_opens_nothing(store: tuple[Path, MemoryKeyStore, list[Path]]) -> None:
    root, keystore, cases = store
    with open_case(cases[0], PASSPHRASE, keystore) as case:
        before = len(case.entries)
    with pytest.raises(KeyCustodyError):
        verify_store(root, "not the right passphrase at all", keystore)
    with open_case(cases[0], PASSPHRASE, keystore) as case:
        assert len(case.entries) == before


def test_cases_that_cannot_be_checked_are_reported(store: tuple[Path, MemoryKeyStore, list[Path]]) -> None:
    root, keystore, cases = store
    (cases[0] / "LOCK").write_text("open elsewhere", encoding="utf-8")
    (root / "1b4e28ba-2fa1-11d2-883f-0016d3cca427").mkdir()  # a case folder without case.json
    results = {r.case_id: r for r in verify_store(root, PASSPHRASE, keystore)}
    locked = results[cases[0].name]
    assert (locked.state, locked.checked, locked.ok) == ("locked", False, True)
    invalid = results["1b4e28ba-2fa1-11d2-883f-0016d3cca427"]
    assert (invalid.state, invalid.ok) == ("invalid", False)


def test_cli_and_sidecar(
    store: tuple[Path, MemoryKeyStore, list[Path]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, keystore, cases = store
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    assert main(["verify-store", "--store", str(root)]) == 0
    shown = capsys.readouterr().out
    assert "2 of 2 cases verified" in shown
    assert "KT-2026-2" in shown
    session = Session(keystore_factory=lambda: keystore)
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "store.verify",
        "params": {"store": str(root.resolve()), "passphrase": PASSPHRASE},
    }
    reply = json.loads(handle(json.dumps(message).encode(), session))
    assert {c["case_id"] for c in reply["result"]} == {c.name for c in cases}
    blob = next((cases[1] / "evidence").iterdir())
    blob.write_bytes(blob.read_bytes()[:-1])
    assert main(["verify-store", "--store", str(root)]) == 1
    assert "FAILED" in capsys.readouterr().out
