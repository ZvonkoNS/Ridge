"""Examiner signing identity: an Ed25519 key that signs job reports and custody heads.

Stored as ``<store>/identity.json``: the public key in clear (it is meant to be shared and
registered with the lab, OQ-9) and the private key sealed under a KEK derived from the
examiner passphrase and the OS-keystore device secret.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from ridge.case.crypto import open_sealed, seal, sha256_hex
from ridge.case.keys import SALT_LEN, KdfParams, KeyStore, b64, check_passphrase, derive_kek, device_secret, unb64
from ridge.errors import CaseError, InputRejectedError, IntegrityError, KeyCustodyError
from ridge.image_io import publish, read_bounded

IDENTITY_FILE = "identity.json"
SCHEMA = "ridge.identity/1"
_PURPOSE = b"identity"
MAX_BYTES = 64 * 1024  # an identity file is well under 1 KiB
_MALFORMED = "identity.json is malformed"


@dataclass(frozen=True)
class Signer:
    """An unlocked signing identity."""

    key_id: str
    public_key: bytes
    _private: Ed25519PrivateKey

    def sign(self, data: bytes) -> bytes:
        """Ed25519 signature over `data`."""
        return self._private.sign(data)


def key_id_for(public_key: bytes) -> str:
    """Short, stable identifier of a public key (first 16 hex chars of its SHA-256)."""
    return sha256_hex(public_key)[:16]


def verify_signature(public_key: bytes, signature: bytes, data: bytes) -> bool:
    """Return True if `signature` is a valid Ed25519 signature of `data` by `public_key`."""
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, data)
    except (InvalidSignature, ValueError):
        return False
    return True


def create_identity(store: Path, passphrase: str, keystore: KeyStore, params: KdfParams | None = None) -> Signer:
    """Create the examiner identity for `store` (refuses to replace an existing one)."""
    check_passphrase(passphrase)
    params = params or KdfParams()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    salt = secrets.token_bytes(SALT_LEN)
    kek = derive_kek(passphrase, salt, params, device_secret(keystore, create=True), _PURPOSE)
    raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "key_id": key_id_for(public),
        "public_key": b64(public),
        "kdf": params.to_json(),
        "salt": b64(salt),
        "sealed_private_key": b64(seal(kek, raw, _aad(public))),
    }
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    publish(store / IDENTITY_FILE, json.dumps(record, indent=2).encode("utf-8"))
    return Signer(record["key_id"], public, private)


def public_identity(store: Path) -> tuple[str, bytes]:
    """(key_id, public key) of the store's identity, without unlocking it."""
    return _public(_read(store))


def unlock_identity(store: Path, passphrase: str, keystore: KeyStore) -> Signer:
    """Unlock the signing key; KeyCustodyError on a wrong passphrase or missing device secret."""
    record = _read(store)
    key_id, public = _public(record)  # one read: the file cannot change between the checks
    try:
        salt, sealed, kdf = unb64(record["salt"]), unb64(record["sealed_private_key"]), record["kdf"]
    except (KeyError, TypeError, ValueError, AttributeError):  # binascii.Error is a ValueError
        raise IntegrityError(_MALFORMED) from None
    kek = derive_kek(passphrase, salt, KdfParams.from_json(kdf), device_secret(keystore, create=False), _PURPOSE)
    try:
        raw = open_sealed(kek, sealed, _aad(public))
    except IntegrityError:
        raise KeyCustodyError("cannot unlock the signing identity: wrong passphrase or wrong OS account") from None
    private = Ed25519PrivateKey.from_private_bytes(raw)
    if private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) != public:
        raise IntegrityError("the sealed private key does not match the public key")
    return Signer(key_id, public, private)


def _aad(public: bytes) -> bytes:
    return b"ridge-identity-v1|" + public


def _read(store: Path) -> dict[str, Any]:
    path = store / IDENTITY_FILE
    if not path.is_file():
        raise CaseError(f"no examiner identity in {store}: run `ridge-case identity init --store {store}` first")
    try:
        record = json.loads(read_bounded(path, MAX_BYTES).decode("utf-8"))
    except (InputRejectedError, UnicodeDecodeError, json.JSONDecodeError):
        raise IntegrityError(_MALFORMED) from None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise IntegrityError("identity.json has an unknown format")
    return record


def _public(record: dict[str, Any]) -> tuple[str, bytes]:
    try:
        key_id, public = record["key_id"], unb64(record["public_key"])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise IntegrityError(_MALFORMED) from None
    if not isinstance(key_id, str) or key_id_for(public) != key_id:
        raise IntegrityError("identity.json key id does not match its public key")
    return key_id, public
