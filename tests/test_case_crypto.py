"""Encryption envelope, key custody and signing identity."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import keyring
import pytest
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from keyring.backend import KeyringBackend

from ridge.case.crypto import keyed_name, open_sealed, random_key, seal
from ridge.case.identity import create_identity, public_identity, unlock_identity, verify_signature
from ridge.case.keys import DEVICE_SECRET_NAME, KdfParams, KeyringKeyStore, check_passphrase, derive_kek, device_secret
from ridge.errors import CaseError, IntegrityError, KeyCustodyError, OutputExistsError, WeakPassphraseError
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore

# ---------------------------------------------------------------- envelope


def test_seal_round_trip() -> None:
    key = random_key()
    assert open_sealed(key, seal(key, b"evidence", b"ctx"), b"ctx") == b"evidence"


@pytest.mark.parametrize("damage", ["key", "aad", "byte", "magic", "version", "short"])
def test_any_change_fails_authentication(damage: str) -> None:
    key = random_key()
    blob = bytearray(seal(key, b"evidence bytes", b"ctx"))
    aad, use_key = b"ctx", key
    if damage == "key":
        use_key = random_key()
    elif damage == "aad":
        aad = b"other case"
    elif damage == "byte":
        blob[-1] ^= 1
    elif damage == "magic":
        blob[0:4] = b"XXXX"
    elif damage == "version":
        blob[4] = 9
    else:
        blob = blob[:10]
    with pytest.raises(IntegrityError):
        open_sealed(use_key, bytes(blob), aad)


def test_keyed_names_hide_content_hashes() -> None:
    sha = "ab" * 32
    k1, k2 = random_key(), random_key()
    assert keyed_name(k1, sha) == keyed_name(k1, sha)
    assert keyed_name(k1, sha) != keyed_name(k2, sha)
    assert sha not in keyed_name(k1, sha)


# ---------------------------------------------------------------- keys


def test_short_passphrases_are_refused() -> None:
    with pytest.raises(WeakPassphraseError):
        check_passphrase("short pass")


def test_weak_kdf_parameters_are_refused() -> None:
    with pytest.raises(KeyCustodyError):
        KdfParams(time_cost=1, memory_kib=64 * 1024, parallelism=1)
    with pytest.raises(KeyCustodyError):
        KdfParams(time_cost=3, memory_kib=1024, parallelism=1)


@pytest.mark.parametrize(
    "stored",
    [
        {"time_cost": 3, "memory_kib": 2**40, "parallelism": 1},  # tampered: exhaust memory before authentication
        {"time_cost": 10**9, "memory_kib": 65536, "parallelism": 1},
        {"time_cost": 3, "memory_kib": 65536, "parallelism": 1000},
        {"time_cost": "3", "memory_kib": 65536, "parallelism": 1},
        {"time_cost": 3.5, "memory_kib": 65536, "parallelism": 1},
        {"memory_kib": 65536, "parallelism": 1},
    ],
)
def test_stored_kdf_parameters_are_bounded(stored: dict[str, object]) -> None:
    with pytest.raises(KeyCustodyError):
        KdfParams.from_json(stored)


def test_kek_needs_both_factors() -> None:
    salt, secret = b"s" * 16, b"d" * 32
    base = derive_kek(PASSPHRASE, salt, FAST_KDF, secret, b"case")
    assert derive_kek(PASSPHRASE, salt, FAST_KDF, secret, b"case") == base
    assert derive_kek(PASSPHRASE + "x", salt, FAST_KDF, secret, b"case") != base
    assert derive_kek(PASSPHRASE, salt, FAST_KDF, b"e" * 32, b"case") != base
    assert derive_kek(PASSPHRASE, salt, FAST_KDF, secret, b"identity") != base


def test_device_secret_lifecycle() -> None:
    store = MemoryKeyStore()
    with pytest.raises(KeyCustodyError):
        device_secret(store, create=False)
    created = device_secret(store, create=True)
    assert device_secret(store, create=False) == created
    store.set(DEVICE_SECRET_NAME, b"short")
    with pytest.raises(KeyCustodyError, match="malformed"):
        device_secret(store, create=False)


class _MemoryBackend(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.data: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.data.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.data[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.data:
            raise keyring.errors.PasswordDeleteError(username)
        del self.data[(service, username)]


def test_keyring_adapter_round_trip() -> None:
    backend = _MemoryBackend()
    previous = keyring.get_keyring()
    keyring.set_keyring(backend)
    try:
        store = KeyringKeyStore(service="ridge-test")
        assert store.get("x") is None
        store.set("x", b"\x00\x01secret")
        assert store.get("x") == b"\x00\x01secret"
        store.delete("x")
        store.delete("x")  # deleting twice is fine
        assert store.get("x") is None
    finally:
        keyring.set_keyring(previous)


# ---------------------------------------------------------------- identity


def test_identity_signs_and_unlocks(tmp_path: Path) -> None:
    keystore = MemoryKeyStore()
    signer = create_identity(tmp_path, PASSPHRASE, keystore, FAST_KDF)
    again = unlock_identity(tmp_path, PASSPHRASE, keystore)
    assert again.key_id == signer.key_id == public_identity(tmp_path)[0]
    sig = again.sign(b"report")
    assert verify_signature(signer.public_key, sig, b"report")
    assert not verify_signature(signer.public_key, sig, b"other")
    raw = signer._private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    stored = (tmp_path / "identity.json").read_text(encoding="utf-8")
    assert base64.b64encode(raw).decode() not in stored  # only the sealed private key is stored


def test_identity_denials(tmp_path: Path) -> None:
    keystore = MemoryKeyStore()
    create_identity(tmp_path, PASSPHRASE, keystore, FAST_KDF)
    with pytest.raises(KeyCustodyError, match="wrong passphrase"):
        unlock_identity(tmp_path, PASSPHRASE + "!", keystore)
    with pytest.raises(KeyCustodyError, match="no Ridge device secret"):
        unlock_identity(tmp_path, PASSPHRASE, MemoryKeyStore())  # another OS account
    with pytest.raises(OutputExistsError):
        create_identity(tmp_path, PASSPHRASE, keystore, FAST_KDF)
    with pytest.raises(CaseError, match="no examiner identity"):
        public_identity(tmp_path / "elsewhere")


def test_tampered_identity_is_detected(tmp_path: Path) -> None:
    keystore = MemoryKeyStore()
    create_identity(tmp_path, PASSPHRASE, keystore, FAST_KDF)
    other = tmp_path / "other"
    create_identity(other, PASSPHRASE, keystore, FAST_KDF)
    record = json.loads((tmp_path / "identity.json").read_text(encoding="utf-8"))
    record["public_key"] = json.loads((other / "identity.json").read_text(encoding="utf-8"))["public_key"]
    (tmp_path / "identity.json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(IntegrityError):
        unlock_identity(tmp_path, PASSPHRASE, keystore)
