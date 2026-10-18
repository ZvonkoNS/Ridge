"""Store backups: a byte copy with a manifest, never into an existing folder, every change detected."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ridge.case.backup import MANIFEST, backup_store, check_backup
from ridge.case.cli import main
from ridge.case.file_check import check_exported
from ridge.case.identity import create_identity
from ridge.case.store import open_case
from ridge.errors import IntegrityError, OutputExistsError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file


@pytest.fixture
def store(tmp_path: Path) -> tuple[Path, MemoryKeyStore, Path]:
    keystore = MemoryKeyStore()
    root = tmp_path / "store"
    create_identity(root, PASSPHRASE, keystore, FAST_KDF)
    case_dir = new_case(root, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        case.import_evidence(photo_file(tmp_path / "in"))
    return root, keystore, case_dir


def test_a_backup_is_an_exact_copy_that_opens(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, keystore, case_dir = store
    manifest = backup_store(root, tmp_path / "backup")
    assert any(f["path"].endswith("identity.json") for f in manifest["files"])
    assert check_backup(tmp_path / "backup").files == len(manifest["files"])
    copy = tmp_path / "backup" / case_dir.name
    with open_case(copy, PASSPHRASE, keystore) as case:  # the copy decrypts with the same secrets
        assert len(case.items()) == 1
    with pytest.raises(OutputExistsError):
        backup_store(root, tmp_path / "backup")
    assert not list(root.rglob("LOCK"))  # the locks held for the copy are released
    assert not any(f["path"].endswith("LOCK") for f in manifest["files"])


def test_only_a_ridge_store_is_backed_up(tmp_path: Path) -> None:
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "letter.txt").write_text("not a store", encoding="utf-8")
    with pytest.raises(ParameterError, match="not a Ridge case store"):
        backup_store(tmp_path / "documents", tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_a_backup_inside_the_store_is_refused(store: tuple[Path, MemoryKeyStore, Path]) -> None:
    root, _, case_dir = store
    for inside in (root / "backup", case_dir / "backup"):
        with pytest.raises(ParameterError, match="outside the case store"):
            backup_store(root, inside)
        assert not inside.exists()


def test_an_open_case_is_not_backed_up(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, keystore, case_dir = store
    with open_case(case_dir, PASSPHRASE, keystore), pytest.raises(ParameterError, match="open"):
        backup_store(root, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


@pytest.mark.parametrize("change", ["edit", "add", "remove", "manifest"])
def test_changes_to_a_backup_are_detected(
    store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path, change: str
) -> None:
    root, _, case_dir = store
    backup_store(root, tmp_path / "backup")
    copy = Path(shutil.copytree(tmp_path / "backup", tmp_path / "copy"))
    blob = next((copy / case_dir.name / "evidence").iterdir())
    if change == "edit":
        blob.write_bytes(blob.read_bytes()[:-1] + b"x")
    elif change == "add":
        (copy / "stray.txt").write_text("x", encoding="utf-8")
    elif change == "remove":
        blob.unlink()
    else:
        (copy / MANIFEST).write_text("{}", encoding="utf-8")
    with pytest.raises(IntegrityError):
        check_backup(copy)


def test_cli(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _, _ = store
    assert main(["backup", "--store", str(root), "--to", str(tmp_path / "b")]) == 0
    assert "OS-keystore secret" in capsys.readouterr().out
    assert main(["check-backup", str(tmp_path / "b")]) == 0
    assert "backup verified" in capsys.readouterr().out
    assert main(["check", str(tmp_path / "b")]) == 0  # the generic check knows a backup folder too
    assert "Store backup: verified" in capsys.readouterr().out
    shown = check_exported(tmp_path / "b")
    assert (shown.kind, shown.key_id) == ("backup", None)
    assert "every file matches the manifest" in shown.details[0]
    (tmp_path / "b" / "extra").write_text("x", encoding="utf-8")
    assert main(["check-backup", str(tmp_path / "b")]) == 1
    with pytest.raises(IntegrityError):
        check_exported(tmp_path / "b")


def test_sidecar_backup(store: tuple[Path, MemoryKeyStore, Path], tmp_path: Path) -> None:
    root, keystore, _ = store
    session = Session(keystore_factory=lambda: keystore)
    params = {"store": str(root.resolve()), "dest": str((tmp_path / "gui-backup").resolve())}
    message = {"jsonrpc": "2.0", "id": 1, "method": "store.backup", "params": params}
    reply = json.loads(handle(json.dumps(message).encode(), session))
    assert reply["result"]["files"] == check_backup(tmp_path / "gui-backup").files
