"""Device-secret recovery (ADR-012): export, import into a new account, refusals, tampering, audit."""

from __future__ import annotations

import getpass
import json
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from ridge.case import cli_common, cli_recovery, recovery, store_audit
from ridge.case.cli import main
from ridge.case.crypto import seal
from ridge.case.identity import create_identity
from ridge.case.keys import DEVICE_SECRET_NAME, b64, derive_kek, unb64
from ridge.case.recovery import NOTICE, export_recovery, fingerprint, import_recovery, read_recovery
from ridge.case.store import open_case
from ridge.case.store_audit import FILE as AUDIT_FILE
from ridge.case.store_audit import append_audit, read_audit
from ridge.errors import CaseLockedError, IntegrityError, KeyCustodyError, OutputExistsError, WeakPassphraseError
from ridge.sidecar import recovery_methods
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case

RECOVERY = "a separate recovery passphrase for the safe"


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, MemoryKeyStore, Path]:
    keystore = MemoryKeyStore()
    root = tmp_path / "store"
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(root, keystore)
    return root, keystore, case_dir


def export(root: Path, keystore: MemoryKeyStore, dest: Path, examiner: str = PASSPHRASE, rec: str = RECOVERY) -> Any:
    return export_recovery(root, examiner, rec, keystore, dest, params=FAST_KDF)


def test_a_new_account_opens_the_cases_again(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, old_account, case_dir = store
    secret = old_account.values[DEVICE_SECRET_NAME]
    dest = tmp_path / "recovery.json"
    info = export(root, old_account, dest)
    text = dest.read_text(encoding="utf-8")
    assert NOTICE in text  # says on its face what it is
    assert secret.hex() not in text
    assert b64(secret) not in text
    assert info.fingerprint == fingerprint(secret)
    new_account = MemoryKeyStore()
    with pytest.raises(KeyCustodyError):
        open_case(case_dir, PASSPHRASE, new_account)  # a store backup alone does not open elsewhere
    assert import_recovery(dest, RECOVERY, root, PASSPHRASE, new_account) == info
    assert new_account.values[DEVICE_SECRET_NAME] == secret
    with open_case(case_dir, PASSPHRASE, new_account) as case:
        assert case.meta().case_reference
    logged = read_audit(root)
    assert [e["action"] for e in logged] == ["recovery.export", "recovery.import"]
    assert {e["fingerprint"] for e in logged} == {info.fingerprint}
    assert logged[0]["destination"] == str(dest.resolve())


def test_export_refusals_write_nothing(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, keystore, _ = store
    dest = tmp_path / "recovery.json"
    with pytest.raises(WeakPassphraseError, match="not be the examiner"):
        export(root, keystore, dest, rec=PASSPHRASE)
    with pytest.raises(WeakPassphraseError):
        export(root, keystore, dest, rec="short")
    with pytest.raises(KeyCustodyError):
        export(root, keystore, dest, examiner="not the examiner passphrase at all")
    assert not dest.exists()
    assert read_audit(root) == []
    dest.write_text("already here", encoding="utf-8")
    with pytest.raises(OutputExistsError):
        export(root, keystore, dest)
    assert dest.read_text(encoding="utf-8") == "already here"  # never replaced


def test_import_refusals_change_nothing(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, old_account, _ = store
    dest = tmp_path / "recovery.json"
    export(root, old_account, dest)
    new_account = MemoryKeyStore()
    with pytest.raises(KeyCustodyError, match="wrong recovery passphrase"):
        import_recovery(dest, "not the recovery passphrase", root, PASSPHRASE, new_account)
    with pytest.raises(KeyCustodyError):
        import_recovery(dest, RECOVERY, root, "not the examiner passphrase at all", new_account)
    assert new_account.values == {}
    other = MemoryKeyStore()
    other.values[DEVICE_SECRET_NAME] = b"\x01" * 32
    with pytest.raises(KeyCustodyError, match="never replaced"):
        import_recovery(dest, RECOVERY, root, PASSPHRASE, other)
    assert other.values[DEVICE_SECRET_NAME] == b"\x01" * 32
    elsewhere = tmp_path / "other-store"
    create_identity(elsewhere, PASSPHRASE, MemoryKeyStore(), FAST_KDF)
    with pytest.raises(IntegrityError, match="made for key"):
        import_recovery(dest, RECOVERY, elsewhere, PASSPHRASE, MemoryKeyStore())
    assert [e["action"] for e in read_audit(root)] == ["recovery.export"]


def test_an_import_that_cannot_be_logged_does_not_happen(
    store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, old_account, _ = store
    dest = tmp_path / "recovery.json"
    export(root, old_account, dest)

    def no_log(*args: object, **kwargs: object) -> None:
        raise OSError("the store is read-only")

    monkeypatch.setattr(recovery, "append_audit", no_log)
    new_account = MemoryKeyStore()
    with pytest.raises(OSError, match="read-only"):
        import_recovery(dest, RECOVERY, root, PASSPHRASE, new_account)
    assert new_account.values == {}


TAMPERS: list[Callable[[dict[str, Any]], Any]] = [
    lambda r: {**r, "key_id": "0" * 16},
    lambda r: {**r, "fingerprint": "0" * 16},
    lambda r: {**r, "created_utc": "2020-01-01T00:00:00Z"},
    lambda r: {**r, "sealed_secret": b64(b"\x00" * 60)},
    lambda r: {**r, "extra": 1},
    lambda r: {**r, "schema": "ridge.something-else/1"},
    lambda r: {**r, "salt": "not base64!"},
    lambda r: {**r, "key_id": 5},
    lambda r: {**r, "notice": "an edited notice"},
    lambda r: {**r, "notice": 5},
    lambda r: [],
]


def test_unreadable_files_and_a_secret_that_is_not_its_fingerprint(
    store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path
) -> None:
    root, old_account, _ = store
    dest = tmp_path / "recovery.json"
    export(root, old_account, dest)
    record = json.loads(dest.read_text(encoding="utf-8"))
    swapped = tmp_path / "swapped.json"  # sealed correctly, but a different secret than its fingerprint names
    kek = derive_kek(RECOVERY, unb64(record["salt"]), FAST_KDF, b"", b"device-secret-recovery")
    aad = f"ridge-device-secret-recovery-v1|{record['key_id']}|{record['fingerprint']}|{record['created_utc']}"
    swapped_record = {**record, "sealed_secret": b64(seal(kek, b"\x02" * 32, aad.encode()))}
    swapped.write_text(json.dumps(swapped_record), encoding="utf-8")
    with pytest.raises(IntegrityError, match="does not match its fingerprint"):
        import_recovery(swapped, RECOVERY, root, PASSPHRASE, MemoryKeyStore())
    garbage = tmp_path / "garbage.json"
    garbage.write_bytes(bytes([0xFF, 0x00]))
    with pytest.raises(IntegrityError, match="not a readable"):
        read_recovery(garbage)


@pytest.mark.parametrize("tamper", TAMPERS)
def test_a_changed_file_is_refused(
    store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path, tamper: Callable[[dict[str, Any]], Any]
) -> None:
    root, old_account, _ = store
    dest = tmp_path / "recovery.json"
    export(root, old_account, dest)
    dest.write_text(json.dumps(tamper(json.loads(dest.read_text(encoding="utf-8")))), encoding="utf-8")
    new_account = MemoryKeyStore()
    with pytest.raises((IntegrityError, KeyCustodyError)):
        import_recovery(dest, RECOVERY, root, PASSPHRASE, new_account)
    assert new_account.values == {}


def test_this_account_notices_removed_or_replaced_entries(
    store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path
) -> None:
    root, keystore, _ = store
    export(root, keystore, tmp_path / "a.json")
    export(root, keystore, tmp_path / "b.json")
    path = root / AUDIT_FILE
    whole = path.read_text(encoding="utf-8")
    first_line = whole.splitlines(keepends=True)[0]
    path.write_text(first_line, encoding="utf-8")  # the last entry cut off: the chain alone still looks fine
    assert len(read_audit(root)) == 1
    with pytest.raises(IntegrityError, match="entries were removed"):
        read_audit(root, keystore)
    path.unlink()
    with pytest.raises(IntegrityError, match="entries were removed"):
        read_audit(root, keystore)
    path.write_text(first_line, encoding="utf-8")
    append_audit(root, MemoryKeyStore(), "something.else")  # a valid chain, but not the entry this account wrote
    with pytest.raises(IntegrityError, match="was replaced"):
        read_audit(root, keystore)
    path.write_text(whole, encoding="utf-8")
    assert len(read_audit(root, keystore)) == 2


def test_appends_wait_for_the_store_audit_lock(
    store: tuple[Path, MemoryKeyStore, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, keystore, _ = store
    monkeypatch.setattr(store_audit, "LOCK_TIMEOUT_S", 0.2)
    held = store_audit._locked(root)  # as if another process held the lock
    with held, pytest.raises(CaseLockedError, match="another Ridge process"):
        append_audit(root, keystore, "something")
    assert append_audit(root, keystore, "something")["seq"] == 0  # free again


def test_a_malformed_head_record_and_a_store_without_identity(tmp_path: Path) -> None:
    root = tmp_path / "store"
    keystore = MemoryKeyStore()
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    append_audit(root, keystore, "something")
    (name,) = [n for n in keystore.values if n.startswith(store_audit.ANCHOR_PREFIX)]
    keystore.values[name] = b"{not json"
    with pytest.raises(IntegrityError, match="head is malformed"):
        read_audit(root, keystore)
    bare = tmp_path / "bare"
    bare.mkdir()
    other = MemoryKeyStore()
    assert append_audit(bare, other, "something")["seq"] == 0
    assert other.values == {}  # no identity, so no head to record
    assert len(read_audit(bare, other)) == 1


def test_the_audit_chain_detects_changes(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, keystore, _ = store
    export(root, keystore, tmp_path / "a.json")
    export(root, keystore, tmp_path / "b.json")
    path = root / AUDIT_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[1] + "\n", encoding="utf-8")  # the first entry removed
    with pytest.raises(IntegrityError, match="chain is broken"):
        read_audit(root)
    edited = json.loads(lines[0])
    edited["destination"] = "elsewhere"
    path.write_text(json.dumps(edited) + "\n" + lines[1] + "\n", encoding="utf-8")
    with pytest.raises(IntegrityError, match="was changed"):
        read_audit(root)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(IntegrityError, match="not a readable"):
        read_audit(root)


def test_cli(
    store: tuple[Path, MemoryKeyStore, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, old_account, _ = store
    answers: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": answers.pop(0))
    monkeypatch.setattr(cli_recovery, "export_recovery", partial(export_recovery, params=FAST_KDF))  # fast KDF
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: old_account)
    dest = tmp_path / "recovery.json"
    answers[:] = [PASSPHRASE, RECOVERY, RECOVERY]
    assert main(["recovery", "export", "--store", str(root), "--to", str(dest)]) == 0
    assert "keep it apart from the recovery passphrase" in capsys.readouterr().out
    assert main(["recovery", "check", str(dest)]) == 0
    info, _ = read_recovery(dest)
    assert f"secret fingerprint {info.fingerprint}" in capsys.readouterr().out
    new_account = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: new_account)
    answers[:] = [RECOVERY, PASSPHRASE]
    assert main(["recovery", "import", str(dest), "--store", str(root)]) == 0
    assert "restored into this account's OS keystore" in capsys.readouterr().out
    answers[:] = [RECOVERY, PASSPHRASE]
    assert main(["recovery", "import", str(dest), "--store", str(root)]) == 1  # never replaced
    assert "never replaced" in capsys.readouterr().err


def test_sidecar(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, old_account, _ = store
    monkeypatch.setattr(recovery_methods, "export_recovery", partial(export_recovery, params=FAST_KDF))
    new_account = MemoryKeyStore()
    accounts = {"current": old_account}
    session = Session(keystore_factory=lambda: accounts["current"])

    def rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        reply: dict[str, Any] = json.loads(handle(json.dumps(message).encode(), session))
        return reply

    dest = (tmp_path / "recovery.json").resolve()
    base = {"store": str(root.resolve()), "examiner_passphrase": PASSPHRASE, "recovery_passphrase": RECOVERY}
    made = rpc("recovery.export", {**base, "dest": str(dest)})["result"]
    assert set(made) == {"key_id", "fingerprint", "created_utc", "file"}  # never the secret
    checked = rpc("recovery.check", {"path": str(dest), "recovery_passphrase": RECOVERY})["result"]
    assert checked["fingerprint"] == made["fingerprint"]
    wrong = rpc("recovery.check", {"path": str(dest), "recovery_passphrase": "not the recovery passphrase"})
    assert wrong["error"]["code"] == -32000  # a refusal: the prompt window may try again
    accounts["current"] = new_account
    restored = rpc("recovery.import", {**base, "path": str(dest)})["result"]
    assert restored["fingerprint"] == made["fingerprint"]
    assert new_account.values[DEVICE_SECRET_NAME] == old_account.values[DEVICE_SECRET_NAME]
    assert rpc("recovery.check", {"path": "relative.json", "recovery_passphrase": RECOVERY})["error"]
