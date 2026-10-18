"""Device-secret recovery file (ADR-012, accepted by the product owner on 2026-10-18).

Every key-encryption key of an examiner account combines the examiner passphrase with a device
secret kept in that account's OS keystore. Store backups do not carry the secret, so losing the
keystore would lose the account's cases. `export_recovery` seals the secret under a separate
recovery passphrase (Argon2id, AES-256-GCM) into ``ridge.device-secret-recovery/1``; the
laboratory keeps the file and the passphrase apart. `import_recovery` restores it into a new
account's keystore.

Rules from ADR-012:

* the recovery passphrase meets the new-passphrase policy and is never the examiner's;
* export needs the examiner passphrase (the examiner is present);
* import never overwrites an existing device secret, and before writing it checks that the
  secret unlocks the store's identity with the examiner passphrase, so a wrong file cannot lock
  anyone out;
* both are logged in the store audit file (no case is open);
* the file says on its face what it is and holds no evidence.

The recovery file replaces only the device factor: opening a case still needs the examiner
passphrase.
"""

from __future__ import annotations

import json
import secrets
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ridge.case.case_model import publish_logged
from ridge.case.crypto import KEY_LEN, open_sealed, seal, sha256_hex
from ridge.case.custody import utc_now
from ridge.case.identity import public_identity, unlock_identity
from ridge.case.keys import (
    DEVICE_SECRET_NAME,
    SALT_LEN,
    KdfParams,
    KeyStore,
    b64,
    check_passphrase,
    derive_kek,
    device_secret,
    unb64,
)
from ridge.case.store_audit import append_audit
from ridge.errors import InputRejectedError, IntegrityError, KeyCustodyError, WeakPassphraseError
from ridge.image_io import read_bounded

SCHEMA = "ridge.device-secret-recovery/1"
NOTICE = (
    "Ridge device-secret recovery file. It holds the OS-keystore secret of one examiner account, sealed under a "
    "recovery passphrase. It holds no evidence. Keep it apart from that passphrase."
)
MAX_BYTES = 16 * 1024
_PURPOSE = b"device-secret-recovery"
_NO_DEVICE_SECRET = b""  # the file must open on another account: the recovery passphrase alone unlocks it
_FIELDS = {"schema", "notice", "created_utc", "key_id", "fingerprint", "kdf", "salt", "sealed_secret"}
_NOT_A_RECOVERY_FILE = "this is not a readable Ridge device-secret recovery file"


@dataclass(frozen=True)
class RecoveryFile:
    """What a recovery file says about itself (nothing secret)."""

    key_id: str  # the examiner identity the secret was checked against at export
    fingerprint: str
    created_utc: str


class _OneSecret:
    """A keystore holding only a candidate secret, to test it before anything is written."""

    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def get(self, name: str) -> bytes | None:
        return self._secret if name == DEVICE_SECRET_NAME else None

    def set(self, name: str, value: bytes) -> None:  # pragma: no cover - never called by unlock
        raise KeyCustodyError("the candidate keystore is read-only")

    def delete(self, name: str) -> None:  # pragma: no cover - never called by unlock
        raise KeyCustodyError("the candidate keystore is read-only")


def fingerprint(secret: bytes) -> str:
    """Return a short, non-reversible name for a device secret, to match a file to an account."""
    return sha256_hex(b"ridge-device-secret-fingerprint|" + secret)[:16]


def _aad(key_id: str, print_: str, created_utc: str) -> bytes:
    return f"ridge-device-secret-recovery-v1|{key_id}|{print_}|{created_utc}".encode()


def export_recovery(
    store: Path,
    examiner_passphrase: str,
    recovery_passphrase: str,
    keystore: KeyStore,
    dest: Path,
    *,
    params: KdfParams | None = None,
) -> RecoveryFile:
    """Seal this account's device secret into a new file at `dest` (logged in the store audit file)."""
    check_passphrase(recovery_passphrase)
    if unicodedata.normalize("NFC", recovery_passphrase) == unicodedata.normalize("NFC", examiner_passphrase):
        raise WeakPassphraseError("the recovery passphrase must not be the examiner passphrase")
    signer = unlock_identity(store, examiner_passphrase, keystore)  # the examiner is present
    secret = device_secret(keystore, create=False)
    params = params or KdfParams()
    salt = secrets.token_bytes(SALT_LEN)
    info = RecoveryFile(signer.key_id, fingerprint(secret), utc_now())
    kek = derive_kek(recovery_passphrase, salt, params, _NO_DEVICE_SECRET, _PURPOSE)
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "notice": NOTICE,
        "created_utc": info.created_utc,
        "key_id": info.key_id,
        "fingerprint": info.fingerprint,
        "kdf": params.to_json(),
        "salt": b64(salt),
        "sealed_secret": b64(seal(kek, secret, _aad(info.key_id, info.fingerprint, info.created_utc))),
    }
    publish_logged(
        [(dest, json.dumps(record, indent=2).encode("utf-8"))],
        lambda: append_audit(
            store,
            keystore,
            "recovery.export",
            key_id=info.key_id,
            fingerprint=info.fingerprint,
            destination=str(dest.resolve()),
        ),
        overwrite=False,
    )
    return info


def read_recovery(path: Path) -> tuple[RecoveryFile, dict[str, Any]]:
    """Parse a recovery file without opening it: what it says about itself, and the record."""
    try:
        record = json.loads(read_bounded(path, MAX_BYTES).decode("utf-8"))
    except (InputRejectedError, UnicodeDecodeError, json.JSONDecodeError):
        raise IntegrityError(_NOT_A_RECOVERY_FILE) from None
    if not isinstance(record, dict) or set(record) != _FIELDS or record["schema"] != SCHEMA:
        raise IntegrityError(_NOT_A_RECOVERY_FILE)
    if record["notice"] != NOTICE:  # the warning on the file's face is part of what Ridge wrote
        raise IntegrityError("the recovery file's notice was changed")
    if not all(isinstance(record[k], str) for k in ("created_utc", "key_id", "fingerprint")):
        raise IntegrityError(_NOT_A_RECOVERY_FILE)
    return RecoveryFile(record["key_id"], record["fingerprint"], record["created_utc"]), record


def open_recovery(path: Path, recovery_passphrase: str) -> tuple[RecoveryFile, bytes]:
    """Open a recovery file with its passphrase; KeyCustodyError on a wrong passphrase."""
    info, record = read_recovery(path)
    try:
        salt, sealed = unb64(record["salt"]), unb64(record["sealed_secret"])
    except (TypeError, ValueError, AttributeError):  # binascii.Error is a ValueError
        raise IntegrityError(_NOT_A_RECOVERY_FILE) from None
    params = KdfParams.from_json(record["kdf"])
    kek = derive_kek(recovery_passphrase, salt, params, _NO_DEVICE_SECRET, _PURPOSE)
    try:
        secret = open_sealed(kek, sealed, _aad(info.key_id, info.fingerprint, info.created_utc))
    except IntegrityError:
        raise KeyCustodyError(
            "cannot open the recovery file: wrong recovery passphrase, or the file was changed"
        ) from None
    if len(secret) != KEY_LEN or fingerprint(secret) != info.fingerprint:
        raise IntegrityError("the recovery file's secret does not match its fingerprint")
    return info, secret


def import_recovery(
    path: Path, recovery_passphrase: str, store: Path, examiner_passphrase: str, keystore: KeyStore
) -> RecoveryFile:
    """Restore a device secret into an account that has none, after proving it opens `store`."""
    info, secret = open_recovery(path, recovery_passphrase)
    if keystore.get(DEVICE_SECRET_NAME) is not None:
        raise KeyCustodyError("this account's OS keystore already holds a Ridge device secret; it is never replaced")
    key_id, _ = public_identity(store)
    if key_id != info.key_id:
        raise IntegrityError(f"the recovery file was made for key {info.key_id}; this store's identity is {key_id}")
    unlock_identity(store, examiner_passphrase, _OneSecret(secret))  # the right secret and the examiner present
    keystore.set(DEVICE_SECRET_NAME, secret)
    try:
        append_audit(
            store,
            keystore,
            "recovery.import",
            key_id=info.key_id,
            fingerprint=info.fingerprint,
            source=str(path.resolve()),
        )
    except BaseException:
        keystore.delete(DEVICE_SECRET_NAME)  # an import that cannot be logged does not happen
        raise
    return info
