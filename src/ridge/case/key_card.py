"""Key cards: how an examiner or the FQM hands a public key to the laboratory's register (OQ-9).

A card (``ridge.key-card/1``) holds the key id, the public key, the role, the holder's name as
they typed it and the time, signed with the key itself. The signature proves that whoever made
the card held the private key; it does not prove who they are, which the laboratory confirms in
person before it adds the card to its register. ``register_add`` writes a new register file with
the card's key added; the previous register is never changed.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import rfc8785

from ridge.case.custody import utc_now
from ridge.case.identity import Signer, key_id_for, verify_signature
from ridge.case.key_register import MAX_BYTES, ROLES, SCHEMA, load_register, parse_register, register_text
from ridge.case.keys import b64
from ridge.errors import IntegrityError, ParameterError
from ridge.image_io import publish, read_bounded

CARD_SCHEMA = "ridge.key-card/1"
MAX_CARD_BYTES = 8 * 1024
STATEMENT = "I hold the private key of this public key and use it for Ridge signatures in the role named here."


@dataclass(frozen=True)
class KeyCard:
    """A card whose self-signature verified."""

    key_id: str
    public_key: str
    role: str
    holder: str
    created_utc: str


def write_card(signer: Signer, role: str, holder: str, dest: Path, *, overwrite: bool = False) -> KeyCard:
    """Write a self-signed card for `signer`'s key."""
    if role not in ROLES:
        raise ParameterError(f"the role must be one of {', '.join(ROLES)}")
    body: dict[str, Any] = {
        "schema": CARD_SCHEMA,
        "key_id": signer.key_id,
        "public_key": b64(signer.public_key),
        "role": role,
        "holder": register_text(holder, "the holder"),
        "created_utc": utc_now(),
        "statement": STATEMENT,
    }
    body["signature"] = b64(signer.sign(bytes(rfc8785.dumps(body))))
    publish(dest, bytes(rfc8785.dumps(body)), overwrite=overwrite)
    return KeyCard(signer.key_id, body["public_key"], role, body["holder"], body["created_utc"])


def check_card(path: Path) -> KeyCard:
    """Verify a card's self-signature and key id (proof of possession, not of identity)."""
    data = read_bounded(path, MAX_CARD_BYTES)
    try:
        card = json.loads(data.decode("utf-8"))
        public = base64.b64decode(str(card["public_key"]), validate=True)
        signature = base64.b64decode(str(card["signature"]), validate=True)
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, binascii.Error):
        raise IntegrityError("not a Ridge key card") from None
    expected = {"schema", "key_id", "public_key", "role", "holder", "created_utc", "statement", "signature"}
    if not isinstance(card, dict) or set(card) != expected or card["schema"] != CARD_SCHEMA:
        raise IntegrityError("not a ridge.key-card/1 file")
    body = bytes(rfc8785.dumps({k: v for k, v in card.items() if k != "signature"}))
    if key_id_for(public) != card["key_id"] or not verify_signature(public, signature, body):
        raise IntegrityError("the key card's signature does not verify: it was changed or not made with this key")
    if card["role"] not in ROLES:
        raise IntegrityError("the key card names an unknown role")
    return KeyCard(card["key_id"], card["public_key"], card["role"], card["holder"], card["created_utc"])


def register_add(
    card: KeyCard,
    dest: Path,
    *,
    register: Path | None = None,
    laboratory: str | None = None,
    valid_from: date,
    valid_until: date | None = None,
    overwrite: bool = False,
) -> int:
    """Write a new register at `dest`: the old one (or an empty one for `laboratory`) plus the card's key."""
    if register is not None:
        doc = json.loads(read_bounded(register, MAX_BYTES).decode("utf-8"))
        load_register(register)  # the old register must be valid before anything is added
    elif laboratory:
        doc = {"schema": SCHEMA, "laboratory": laboratory, "keys": []}
    else:
        raise ParameterError("give the existing register, or the laboratory's name for a new one")
    if any(k.get("key_id") == card.key_id for k in doc["keys"]):
        raise ParameterError(f"key {card.key_id} is already in the register")
    entry: dict[str, Any] = {
        "key_id": card.key_id,
        "public_key": card.public_key,
        "holder": card.holder,
        "role": card.role,
        "valid_from": valid_from.isoformat(),
    }
    if valid_until is not None:
        entry["valid_until"] = valid_until.isoformat()
    doc["keys"].append(entry)
    data = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    parse_register(data)  # the result must be a valid register
    publish(dest, data, overwrite=overwrite)
    return len(doc["keys"])
