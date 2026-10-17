"""Key custody: examiner passphrase (Argon2id) combined with an OS-keystore device secret.

A key-encryption key (KEK) needs BOTH factors (architecture §8.2, ADR-004)::

    KEK = HKDF-SHA256(Argon2id(passphrase, salt) || device_secret, info=purpose)

The device secret is a random 256-bit value kept in the OS keystore of the examiner's
account (Windows Credential Locker / macOS Keychain / Linux Secret Service), so a copied
disk is useless without that account, and the account is useless without the passphrase.
"""

from __future__ import annotations

import base64
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Protocol

import keyring
import keyring.errors
from argon2.low_level import Type, hash_secret_raw

from ridge.case.crypto import KEY_LEN, derive_subkey, random_key
from ridge.errors import KeyCustodyError, WeakPassphraseError

KEYRING_SERVICE = "ridge"
DEVICE_SECRET_NAME = "device-secret-v1"  # noqa: S105  # nosec B105 - keystore entry name, not a secret
MIN_PASSPHRASE_CHARS = 15  # NIST SP 800-63B-style length rule, no composition rules
SALT_LEN = 16


@dataclass(frozen=True)
class KdfParams:
    """Argon2id cost parameters; stored with each wrapped key so they can be raised later."""

    time_cost: int = 3
    memory_kib: int = 256 * 1024
    parallelism: int = 4

    MIN_TIME_COST: ClassVar[int] = 3
    MIN_MEMORY_KIB: ClassVar[int] = 64 * 1024  # RFC 9106 second recommended option
    # Upper bounds: parameters are read from case.json before anything is authenticated, so a
    # tampered file must not be able to make unlocking exhaust memory or stall (CWE-400).
    MAX_TIME_COST: ClassVar[int] = 10
    MAX_MEMORY_KIB: ClassVar[int] = 1024 * 1024
    MAX_PARALLELISM: ClassVar[int] = 16

    def __post_init__(self) -> None:
        if not (
            self.MIN_TIME_COST <= self.time_cost <= self.MAX_TIME_COST
            and self.MIN_MEMORY_KIB <= self.memory_kib <= self.MAX_MEMORY_KIB
            and 1 <= self.parallelism <= self.MAX_PARALLELISM
        ):
            raise KeyCustodyError(
                "Argon2id parameters are out of range (t 3-10, m 64 MiB-1 GiB, p 1-16): the key file may be damaged"
            )

    def to_json(self) -> dict[str, int]:
        """JSON form stored next to the wrapped key."""
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> KdfParams:
        """Parse and validate stored (unauthenticated) parameters."""
        try:
            values = [data["time_cost"], data["memory_kib"], data["parallelism"]]
        except (KeyError, TypeError):
            raise KeyCustodyError("the key file has no valid Argon2id parameters") from None
        if not all(type(v) is int for v in values):
            raise KeyCustodyError("the key file's Argon2id parameters are not integers")
        return cls(*values)


class KeyStore(Protocol):
    """Where the per-account device secret lives."""

    def get(self, name: str) -> bytes | None:
        """Return the secret stored under `name`, or None."""
        ...

    def set(self, name: str, value: bytes) -> None:
        """Store `value` under `name`."""
        ...

    def delete(self, name: str) -> None:
        """Remove `name` (no error if absent)."""
        ...


class KeyringKeyStore:
    """KeyStore backed by the OS keystore through ``keyring``."""

    def __init__(self, service: str = KEYRING_SERVICE) -> None:
        self.service = service

    def get(self, name: str) -> bytes | None:
        """Return the secret stored under `name`, or None."""
        try:
            value = keyring.get_password(self.service, name)
        except keyring.errors.KeyringError as exc:
            raise KeyCustodyError(f"OS keystore unavailable: {type(exc).__name__}") from None
        return None if value is None else base64.b64decode(value)

    def set(self, name: str, value: bytes) -> None:
        """Store `value` under `name`."""
        try:
            keyring.set_password(self.service, name, base64.b64encode(value).decode("ascii"))
        except keyring.errors.KeyringError as exc:
            raise KeyCustodyError(f"OS keystore unavailable: {type(exc).__name__}") from None

    def delete(self, name: str) -> None:
        """Remove `name` (no error if absent)."""
        try:
            keyring.delete_password(self.service, name)
        except keyring.errors.PasswordDeleteError:
            return
        except keyring.errors.KeyringError as exc:
            raise KeyCustodyError(f"OS keystore unavailable: {type(exc).__name__}") from None


def check_passphrase(passphrase: str) -> None:
    """Enforce the passphrase policy when a passphrase is set."""
    if len(unicodedata.normalize("NFC", passphrase)) < MIN_PASSPHRASE_CHARS:
        raise WeakPassphraseError(f"the passphrase must have at least {MIN_PASSPHRASE_CHARS} characters")


def device_secret(keystore: KeyStore, *, create: bool) -> bytes:
    """Return this account's device secret, creating it on first use when `create`."""
    secret = keystore.get(DEVICE_SECRET_NAME)
    if secret is None:
        if not create:
            raise KeyCustodyError("the OS keystore has no Ridge device secret for this account")
        secret = random_key()
        keystore.set(DEVICE_SECRET_NAME, secret)
    if len(secret) != KEY_LEN:
        raise KeyCustodyError("the Ridge device secret in the OS keystore is malformed")
    return secret


def derive_kek(passphrase: str, salt: bytes, params: KdfParams, secret: bytes, purpose: bytes) -> bytes:
    """Key-encryption key from passphrase + device secret for one `purpose`."""
    stretched = hash_secret_raw(
        secret=unicodedata.normalize("NFC", passphrase).encode("utf-8"),
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_kib,
        parallelism=params.parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )
    return derive_subkey(stretched + secret, b"ridge-kek-v1|" + purpose)


def b64(data: bytes) -> str:
    """Encode as standard base64 text."""
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    """Decode standard base64 text strictly."""
    return base64.b64decode(text.encode("ascii"), validate=True)
