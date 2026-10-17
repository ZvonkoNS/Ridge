"""Authenticated encryption envelope and key helpers for the case store (architecture §8.2).

Only vetted primitives from ``cryptography`` are used: AES-256-GCM for data, HKDF-SHA256 for
sub-keys and HMAC-SHA256 for file names. No custom cryptography (PRD SEC-4).

Envelope format: ``b"RDG1" | version (1 byte) | nonce (12 bytes) | ciphertext+tag``. The
header is part of the associated data, so it cannot be altered; callers add context (case,
role, content hash) to the associated data so a blob cannot be moved between cases or roles.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ridge.errors import IntegrityError

MAGIC = b"RDG1"
VERSION = 1
KEY_LEN = 32
NONCE_LEN = 12
_HEADER_LEN = len(MAGIC) + 1


def random_key() -> bytes:
    """Return a fresh 256-bit key from the OS CSPRNG."""
    return secrets.token_bytes(KEY_LEN)


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt and authenticate `plaintext` under `key`, binding `aad`."""
    header = MAGIC + bytes([VERSION])
    nonce = secrets.token_bytes(NONCE_LEN)
    return header + nonce + AESGCM(key).encrypt(nonce, plaintext, header + aad)


def open_sealed(key: bytes, blob: bytes, aad: bytes) -> bytes:
    """Decrypt a sealed blob; raises IntegrityError if anything was altered or the key is wrong."""
    if len(blob) < _HEADER_LEN + NONCE_LEN + 16 or blob[: len(MAGIC)] != MAGIC:
        raise IntegrityError("not a Ridge encrypted file")
    if blob[len(MAGIC)] != VERSION:
        raise IntegrityError(f"unsupported encryption format version {blob[len(MAGIC)]}")
    header, nonce, body = (
        blob[:_HEADER_LEN],
        blob[_HEADER_LEN : _HEADER_LEN + NONCE_LEN],
        blob[_HEADER_LEN + NONCE_LEN :],
    )
    try:
        return AESGCM(key).decrypt(nonce, body, header + aad)
    except InvalidTag:
        raise IntegrityError("authentication failed: wrong key or the data was altered") from None


def derive_subkey(key: bytes, info: bytes) -> bytes:
    """Derive an independent 256-bit sub-key (HKDF-SHA256) for one purpose."""
    return HKDF(algorithm=hashes.SHA256(), length=KEY_LEN, salt=None, info=info).derive(key)


def keyed_name(name_key: bytes, content_sha256: str) -> str:
    """File name for content: HMAC-SHA256 so names do not reveal which image is stored (ADR-008)."""
    return hmac.new(name_key, content_sha256.encode("ascii"), hashlib.sha256).hexdigest()


def sha256_hex(data: bytes) -> str:
    """SHA-256 of `data` as lowercase hex."""
    return hashlib.sha256(data).hexdigest()
