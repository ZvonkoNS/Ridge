"""Case overview with one passphrase: references, retention, hold, nothing written."""

from __future__ import annotations

import getpass
import json
from datetime import date
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity
from ridge.case.store import open_case
from ridge.case.store_overview import store_overview
from ridge.errors import KeyCustodyError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, future, new_case, photo_file


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, MemoryKeyStore, list[Path]]:
    keystore = MemoryKeyStore()
    root = tmp_path / "store"
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    cases = [new_case(root, keystore, reference=f"KT-2026-{n}") for n in (1, 2)]
    with open_case(cases[0], PASSPHRASE, keystore) as case:
        case.import_evidence(photo_file(tmp_path / "in"))
        case.set_legal_hold(True, "Court order 1/2026")
    return root, keystore, cases


def test_overview_reads_metadata_and_writes_nothing(store: tuple[Path, MemoryKeyStore, list[Path]]) -> None:
    root, keystore, cases = store
    logs = {c: (c / "custody.jsonl.enc").read_bytes() for c in cases}
    shown = {o.case_id: o for o in store_overview(root, PASSPHRASE, keystore)}
    first, second = shown[cases[0].name], shown[cases[1].name]
    assert (first.reference, first.legal_hold, first.evidence, first.due) == ("KT-2026-1", True, 1, False)
    assert (second.reference, second.legal_hold, second.evidence) == ("KT-2026-2", False, 0)
    assert second.retention_until == future().isoformat()
    assert all((c / "custody.jsonl.enc").read_bytes() == logs[c] for c in cases)  # nothing was logged
    later = {o.case_id: o for o in store_overview(root, PASSPHRASE, keystore, today=date(2100, 1, 1).isoformat())}
    assert (later[cases[0].name].due, later[cases[1].name].due) == (False, True)  # a hold is never due


def test_a_wrong_passphrase_shows_nothing(store: tuple[Path, MemoryKeyStore, list[Path]]) -> None:
    root, keystore, _ = store
    with pytest.raises(KeyCustodyError):
        store_overview(root, "not the right passphrase at all", keystore)


def test_cli_and_sidecar(
    store: tuple[Path, MemoryKeyStore, list[Path]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, keystore, cases = store
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    (cases[1] / "LOCK").write_text("open elsewhere", encoding="utf-8")
    assert main(["overview", "--store", str(root)]) == 0
    shown = capsys.readouterr().out
    assert "KT-2026-1  keep until" in shown
    assert "legal hold" in shown
    assert f"{cases[1].name}  locked" in shown
    session = Session(keystore_factory=lambda: keystore)
    params = {"store": str(root.resolve()), "passphrase": PASSPHRASE}
    message = {"jsonrpc": "2.0", "id": 1, "method": "store.overview", "params": params}
    reply = json.loads(handle(json.dumps(message).encode(), session))
    assert {c["reference"] for c in reply["result"]} == {"KT-2026-1", None}
