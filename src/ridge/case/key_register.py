"""The laboratory's register of signing keys (PRD OQ-9): who holds which key, for which role, when.

Reports, processing records, custody heads, packages and signed limits carry their own public
key, so a valid signature shows only *which* key signed. The laboratory (for example its
Security Owner or Forensic Quality Manager) keeps a ``ridge.key-register/1`` file that lists each
key's holder, role (``examiner`` or ``fqm``) and validity. Given ``--register``, the offline checks
name the holder and refuse a key that is not registered for the role, not yet valid, expired or
revoked at the signing time.

Ridge does not sign the register: the laboratory distributes it, and its SHA-256 is printed so a
reviewer can confirm the version they were given. Signing times come from the signed files, that
is from the signer's clock; a key used before its revocation could backdate a file, which only
countersigned custody heads (OQ-8) rule out.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ridge.case.crypto import sha256_hex
from ridge.case.identity import key_id_for
from ridge.case.keys import unb64
from ridge.errors import IntegrityError, ParameterError
from ridge.image_io import read_bounded

SCHEMA = "ridge.key-register/1"
ROLES = ("examiner", "fqm")
MAX_BYTES = 1024 * 1024
MAX_KEYS = 2000
_CONTROL = re.compile("[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]")
_KEY_FIELDS = {"key_id", "public_key", "holder", "role", "valid_from", "valid_until", "revoked"}


@dataclass(frozen=True)
class RegisteredKey:
    """One key as the laboratory registered it."""

    key_id: str
    holder: str
    role: str
    valid_from: date
    valid_until: date | None
    revoked: date | None


@dataclass(frozen=True)
class KeyRegister:
    """A parsed register and the SHA-256 of the file it came from."""

    laboratory: str
    sha256: str
    keys: dict[str, RegisteredKey]


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200 or _CONTROL.search(value):
        raise ParameterError(f"key register: {what} must be 1-200 printable characters")
    return value.strip()


def _date(value: object, what: str) -> date:
    if isinstance(value, str) and len(value) == 10:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ParameterError(f"key register: {what} must be a date written YYYY-MM-DD")


def _optional_date(value: object, what: str) -> date | None:
    return None if value is None else _date(value, what)


def _key(raw: object, index: int) -> RegisteredKey:
    if (
        not isinstance(raw, dict)
        or not set(raw) <= _KEY_FIELDS
        or not {"key_id", "public_key", "holder", "role"} <= set(raw)
    ):
        raise ParameterError(
            f"key register: key {index} must have key_id, public_key, holder, role and known fields only"
        )
    try:
        public = unb64(str(raw["public_key"]))
    except ValueError:
        raise ParameterError(f"key register: key {index} has a public key that is not base64") from None
    if len(public) != 32 or key_id_for(public) != raw["key_id"]:
        raise ParameterError(f"key register: key {index}'s key id does not match its public key")
    if raw["role"] not in ROLES:
        raise ParameterError(f"key register: key {index}'s role must be one of {', '.join(ROLES)}")
    valid_from = _date(raw.get("valid_from", "1970-01-01"), f"key {index} valid_from")
    valid_until = _optional_date(raw.get("valid_until"), f"key {index} valid_until")
    if valid_until is not None and valid_until < valid_from:
        raise ParameterError(f"key register: key {index} ends before it starts")
    return RegisteredKey(
        key_id=str(raw["key_id"]),
        holder=_text(raw["holder"], f"key {index} holder"),
        role=str(raw["role"]),
        valid_from=valid_from,
        valid_until=valid_until,
        revoked=_optional_date(raw.get("revoked"), f"key {index} revoked"),
    )


def parse_register(data: bytes) -> KeyRegister:
    """Validate a register strictly: known fields only, matching key ids, one entry per key."""
    try:
        doc: Any = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ParameterError("key register: not a UTF-8 JSON document") from None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or set(doc) - {"schema", "laboratory", "keys"}:
        raise ParameterError(f"key register: the schema must be {SCHEMA!r} with laboratory and keys only")
    raw_keys = doc.get("keys")
    if not isinstance(raw_keys, list) or not 1 <= len(raw_keys) <= MAX_KEYS:
        raise ParameterError(f"key register: keys must be a list of 1-{MAX_KEYS} entries")
    keys: dict[str, RegisteredKey] = {}
    for index, raw in enumerate(raw_keys):
        key = _key(raw, index)
        if key.key_id in keys:
            raise ParameterError(f"key register: key {key.key_id} is listed twice")
        keys[key.key_id] = key
    return KeyRegister(_text(doc.get("laboratory"), "laboratory"), sha256_hex(data), keys)


def load_register(path: Path) -> KeyRegister:
    """Read and validate a register file (bounded)."""
    return parse_register(read_bounded(path, MAX_BYTES))


def confirm_key(register: KeyRegister, key_id: str, role: str, signed_utc: str) -> RegisteredKey:
    """Return the registered key that signed at `signed_utc` in `role`, or refuse (IntegrityError)."""
    key = register.keys.get(key_id)
    if key is None:
        raise IntegrityError(f"key {key_id} is not in the {register.laboratory} key register")
    if key.role != role:
        raise IntegrityError(f"key {key_id} is registered for the {key.role} role, not for the {role} role")
    try:
        day = date.fromisoformat(signed_utc[:10])
    except ValueError:
        raise IntegrityError(f"the signing time {signed_utc!r} is not a date") from None
    if day < key.valid_from or (key.valid_until is not None and day > key.valid_until):
        raise IntegrityError(f"key {key_id} was not valid on {day} (register: {key.valid_from} to {key.valid_until})")
    if key.revoked is not None and day >= key.revoked:
        raise IntegrityError(f"key {key_id} was revoked on {key.revoked}, before or on the signing day {day}")
    return key


def describe(register: KeyRegister, key: RegisteredKey) -> str:
    """One line naming the holder and the register version."""
    return (
        f"registered to {key.holder} ({key.role} key {key.key_id}) in the {register.laboratory} key register "
        f"(sha256 {register.sha256[:16]})"
    )
