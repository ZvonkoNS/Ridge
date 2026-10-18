"""Key cards and register-add: proof of possession, never changing the old register."""

from __future__ import annotations

import getpass
import json
from datetime import date
from pathlib import Path

import pytest

from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.key_card import check_card, register_add, write_card
from ridge.case.key_register import confirm_key, load_register
from ridge.case.limits_signing import create_fqm_key
from ridge.errors import IntegrityError, OutputExistsError, ParameterError
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore

FQM_PASSPHRASE = "quality manager's own long passphrase"  # noqa: S105  # synthetic test passphrase


@pytest.fixture
def cards(tmp_path: Path) -> tuple[Path, Path]:
    keystore = MemoryKeyStore()
    create_identity(tmp_path / "store", PASSPHRASE, keystore, FAST_KDF)
    examiner = unlock_identity(tmp_path / "store", PASSPHRASE, keystore)
    fqm = create_fqm_key(tmp_path / "fqm.json", FQM_PASSPHRASE, FAST_KDF)
    write_card(examiner, "examiner", "Examiner A", tmp_path / "a.card.json")
    write_card(fqm, "fqm", "FQM B", tmp_path / "b.card.json")
    return tmp_path / "a.card.json", tmp_path / "b.card.json"


def test_cards_prove_possession_and_tampering_is_detected(cards: tuple[Path, Path], tmp_path: Path) -> None:
    examiner, fqm = cards
    assert (check_card(examiner).role, check_card(fqm).role) == ("examiner", "fqm")
    doc = json.loads(examiner.read_bytes())
    doc["holder"] = "Someone Else"
    (tmp_path / "forged.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(IntegrityError, match="does not verify"):
        check_card(tmp_path / "forged.json")
    doc = json.loads(fqm.read_bytes())
    doc["public_key"], doc["key_id"] = json.loads(examiner.read_bytes())["public_key"], doc["key_id"]
    (tmp_path / "swapped.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(IntegrityError):
        check_card(tmp_path / "swapped.json")
    (tmp_path / "junk.json").write_text("{}", encoding="utf-8")
    with pytest.raises(IntegrityError):
        check_card(tmp_path / "junk.json")


def test_card_text_and_role_are_checked(tmp_path: Path) -> None:
    keystore = MemoryKeyStore()
    create_identity(tmp_path / "store", PASSPHRASE, keystore, FAST_KDF)
    signer = unlock_identity(tmp_path / "store", PASSPHRASE, keystore)
    with pytest.raises(ParameterError):
        write_card(signer, "admin", "Examiner A", tmp_path / "x.json")
    with pytest.raises(ParameterError):
        write_card(signer, "examiner", "Examiner\u202eA", tmp_path / "x.json")
    assert not (tmp_path / "x.json").exists()


def test_register_add_writes_a_new_version(cards: tuple[Path, Path], tmp_path: Path) -> None:
    examiner, fqm = cards
    first = tmp_path / "register-1.json"
    assert register_add(check_card(examiner), first, laboratory="Synthetic Lab", valid_from=date(2026, 1, 1)) == 1
    second = tmp_path / "register-2.json"
    assert register_add(check_card(fqm), second, register=first, valid_from=date(2026, 1, 1)) == 2
    assert len(load_register(first).keys) == 1  # the old version is unchanged
    register = load_register(second)
    key = confirm_key(register, check_card(fqm).key_id, "fqm", "2026-10-18T08:00:00Z")
    assert key.holder == "FQM B"
    with pytest.raises(ParameterError, match="already in the register"):
        register_add(check_card(fqm), tmp_path / "register-3.json", register=second, valid_from=date(2026, 1, 1))
    with pytest.raises(OutputExistsError):
        register_add(check_card(examiner), second, laboratory="Synthetic Lab", valid_from=date(2026, 1, 1))
    with pytest.raises(ParameterError, match="laboratory"):
        register_add(check_card(examiner), tmp_path / "register-4.json", valid_from=date(2026, 1, 1))


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    keystore = MemoryKeyStore()
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(cli_common, "KDF_PARAMS", FAST_KDF)
    create_identity(tmp_path / "store", PASSPHRASE, keystore, FAST_KDF)
    create_fqm_key(tmp_path / "fqm.json", FQM_PASSPHRASE, FAST_KDF)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    card = ["key-card", "--store", str(tmp_path / "store"), "--holder", "Examiner A"]
    assert main([*card, "--to", str(tmp_path / "a.json")]) == 0
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": FQM_PASSPHRASE)
    assert (
        main(
            ["key-card", "--fqm-key", str(tmp_path / "fqm.json"), "--holder", "FQM B", "--to", str(tmp_path / "b.json")]
        )
        == 0
    )
    add = ["register-add", "--card", str(tmp_path / "a.json"), "--laboratory", "Synthetic Lab"]
    assert main([*add, "--to", str(tmp_path / "r1.json"), "--valid-from", "2026-01-01"]) == 0
    add = ["register-add", "--card", str(tmp_path / "b.json"), "--register", str(tmp_path / "r1.json")]
    assert main([*add, "--to", str(tmp_path / "r2.json"), "--valid-until", "2030-12-31"]) == 0
    capsys.readouterr()
    assert main(["register", "--check", str(tmp_path / "r2.json")]) == 0
    shown = capsys.readouterr().out
    assert "Synthetic Lab key register, 2 key(s)" in shown
    assert "FQM B" in shown


def test_sidecar_identity_card(tmp_path: Path) -> None:
    keystore = MemoryKeyStore()
    create_identity(tmp_path / "store", PASSPHRASE, keystore, FAST_KDF)
    session = Session(keystore_factory=lambda: keystore)
    params = {
        "store": str((tmp_path / "store").resolve()),
        "passphrase": PASSPHRASE,
        "holder": "Examiner A",
        "dest": str((tmp_path / "card.json").resolve()),
    }
    message = {"jsonrpc": "2.0", "id": 1, "method": "identity.card", "params": params}
    reply = json.loads(handle(json.dumps(message).encode(), session))
    assert check_card(tmp_path / "card.json").key_id == reply["result"]["key_id"]
    params["passphrase"] = "not the right passphrase at all"  # noqa: S105  # synthetic wrong passphrase
    params["dest"] = str((tmp_path / "other.json").resolve())
    message["params"] = params
    assert "error" in json.loads(handle(json.dumps(message).encode(), session))
    assert not (tmp_path / "other.json").exists()
