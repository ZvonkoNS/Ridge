"""Store listing without a passphrase (FR-50 open flow): ids and states only, nothing decrypted."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ridge.case.dispose import dispose_case
from ridge.case.identity import create_identity
from ridge.case.listing import list_cases
from ridge.case.store import open_case
from ridge.errors import CaseError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    create_identity(tmp_path / "store", PASSPHRASE, keystore, FAST_KDF)
    return tmp_path / "store", keystore


def test_lists_every_state(store: tuple[Path, MemoryKeyStore]) -> None:
    root, keystore = store
    active = new_case(root, keystore, reference="KT-SECRET-REFERENCE")
    locked = new_case(root, keystore)
    disposed = new_case(root, keystore)
    erasing = new_case(root, keystore)
    invalid = new_case(root, keystore)
    dispose_case(
        disposed,
        PASSPHRASE,
        keystore,
        confirm_case_id=disposed.name,
        reason="proceedings-closed",
        actor_key_id="k",
        before_retention=True,
    )
    record = json.loads((root / f"{disposed.name}.disposal.json").read_text(encoding="utf-8"))
    (erasing / "case.json").write_text(
        json.dumps({"schema": "ridge.case-erasing/1", "case_id": erasing.name, "record": record}), encoding="utf-8"
    )
    (invalid / "case.json").write_text("{not json", encoding="utf-8")
    (root / "notes").mkdir()  # not a case folder: skipped
    (root / "not-a-uuid.disposal.json").write_text("{}", encoding="utf-8")

    with open_case(locked, PASSPHRASE, keystore):
        states = {c.case_id: c.state for c in list_cases(root)}
    assert states == {
        active.name: "active",
        locked.name: "locked",
        disposed.name: "disposed",
        erasing.name: "erasing",
        invalid.name: "invalid",
    }
    listing = json.dumps([c.to_json() for c in list_cases(root)])
    assert "KT-SECRET-REFERENCE" not in listing  # nothing encrypted is revealed
    assert all(c.created_utc for c in list_cases(root) if c.state == "active")


def test_case_json_for_another_folder_is_invalid(store: tuple[Path, MemoryKeyStore]) -> None:
    root, keystore = store
    first, second = new_case(root, keystore), new_case(root, keystore)
    (second / "case.json").write_bytes((first / "case.json").read_bytes())
    states = {c.case_id: c.state for c in list_cases(root)}
    assert states[second.name] == "invalid"
    (second / "case.json").write_text(json.dumps({"schema": "other/1", "case_id": second.name}), encoding="utf-8")
    assert {c.case_id: c.state for c in list_cases(root)}[second.name] == "invalid"


def test_missing_store(tmp_path: Path) -> None:
    with pytest.raises(CaseError, match="not a Ridge store"):
        list_cases(tmp_path / "missing")


@pytest.mark.parametrize(
    "content",
    ["{}", '{"schema": "ridge.disposal/1", "case_id": "00000000-0000-0000-0000-000000000000"}', "not json"],
)
def test_damaged_disposal_records_are_invalid(tmp_path: Path, content: str) -> None:
    case_id = "11111111-2222-3333-4444-555555555555"
    (tmp_path / f"{case_id}.disposal.json").write_text(content, encoding="utf-8")
    assert [(c.case_id, c.state) for c in list_cases(tmp_path)] == [(case_id, "invalid")]
