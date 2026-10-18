"""The Forensic Quality Manager's signing key for limits of use (PRD §12 item 8).

The FQM keeps an Ed25519 key in a passphrase-sealed file (``ridge.fqm-key/1``), away from the
examiner workstations; the passphrase alone unlocks it (Argon2id), so the file can move between
machines. ``ridge-case limits --sign FILE --key KEY`` validates the limits file and writes
``FILE.sig`` (``ridge.limits-signature/1``) beside it. Verification is in `limits`.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from ridge.case.crypto import open_sealed, seal, sha256_hex
from ridge.case.identity import Signer, key_id_for
from ridge.case.keys import SALT_LEN, KdfParams, b64, check_passphrase, derive_kek, unb64
from ridge.case.limits import MAX_BYTES, SIGNATURE_SCHEMA, SIGNED_PREFIX, parse_limits
from ridge.errors import IntegrityError, KeyCustodyError
from ridge.image_io import publish, read_bounded

KEY_SCHEMA = "ridge.fqm-key/1"
MAX_KEY_BYTES = 4096
_PURPOSE = b"fqm-limits"
_NO_DEVICE_SECRET = b""  # the key file must work on the FQM's own machine, not one OS account


def _aad(public: bytes) -> bytes:
    return b"ridge-fqm-key-v1|" + public


def create_fqm_key(dest: Path, passphrase: str, params: KdfParams | None = None) -> Signer:
    """Create a sealed FQM key file at `dest` (never replaces an existing file)."""
    check_passphrase(passphrase)
    params = params or KdfParams()
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    salt = secrets.token_bytes(SALT_LEN)
    kek = derive_kek(passphrase, salt, params, _NO_DEVICE_SECRET, _PURPOSE)
    raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    record: dict[str, Any] = {
        "schema": KEY_SCHEMA,
        "key_id": key_id_for(public),
        "public_key": b64(public),
        "kdf": params.to_json(),
        "salt": b64(salt),
        "sealed_private_key": b64(seal(kek, raw, _aad(public))),
    }
    publish(dest, json.dumps(record, indent=2).encode("utf-8"))
    return Signer(record["key_id"], public, private)


def unlock_fqm_key(path: Path, passphrase: str) -> Signer:
    """Unlock an FQM key file; KeyCustodyError on a wrong passphrase."""
    try:
        record = json.loads(read_bounded(path, MAX_KEY_BYTES).decode("utf-8"))
        public = unb64(record["public_key"])
        if record.get("schema") != KEY_SCHEMA or key_id_for(public) != record["key_id"]:
            raise IntegrityError(f"{path.name} is not a Ridge FQM key file")
        kek = derive_kek(
            passphrase, unb64(record["salt"]), KdfParams.from_json(record["kdf"]), _NO_DEVICE_SECRET, _PURPOSE
        )
        sealed = unb64(record["sealed_private_key"])
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError):
        raise IntegrityError(f"{path.name} is not a Ridge FQM key file") from None
    try:
        raw = open_sealed(kek, sealed, _aad(public))
    except IntegrityError:
        raise KeyCustodyError("cannot unlock the FQM key: wrong passphrase") from None
    private = Ed25519PrivateKey.from_private_bytes(raw)
    if private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) != public:
        raise IntegrityError("the sealed FQM key does not match its public key")
    return Signer(record["key_id"], public, private)


def sign_limits(limits_file: Path, key_file: Path, passphrase: str, *, overwrite: bool = False) -> Path:
    """Validate `limits_file`, sign it with the FQM key and write ``limits_file.sig``; return its path."""
    data = read_bounded(limits_file, MAX_BYTES)
    parse_limits(data)  # never sign a file that jobs would refuse
    signer = unlock_fqm_key(key_file, passphrase)
    doc = {
        "schema": SIGNATURE_SCHEMA,
        "key_id": signer.key_id,
        "public_key": b64(signer.public_key),
        "limits_sha256": sha256_hex(data),
        "signature": b64(signer.sign(SIGNED_PREFIX + data)),
    }
    dest = limits_file.with_name(limits_file.name + ".sig")
    publish(dest, json.dumps(doc, indent=2).encode("utf-8"), overwrite=overwrite)
    return dest
