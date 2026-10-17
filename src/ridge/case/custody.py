"""Append-only, hash-chained, encrypted chain-of-custody log (PRD FR-22, architecture §8.4).

Each entry is RFC 8785 canonical JSON. ``prev`` is the SHA-256 of the previous entry's
canonical bytes (64 zeros for the first), and ``seq`` counts from 0. Every line in
``custody.jsonl.enc`` is one entry sealed under the case log key, bound to its sequence number.
``chain.sign`` entries carry an Ed25519 signature over the head hash they close.

Limits (R-5): an offline log cannot prove *when* things happened against a trusted clock, and
cutting entries off the end is only detectable up to the last signed head held elsewhere
(out-of-band countersigning, OQ-8).
"""

from __future__ import annotations

import base64
import getpass
import json
import os
import platform
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import rfc8785

from ridge.case.crypto import open_sealed, seal, sha256_hex
from ridge.case.identity import Signer, verify_signature
from ridge.errors import IntegrityError

LOG_FILE = "custody.jsonl.enc"
GENESIS = "0" * 64
type Entry = dict[str, Any]


def utc_now() -> str:
    """Return the current UTC time as ISO 8601 with a Z suffix, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def default_actor() -> str:
    """OS account and workstation performing the action (stored encrypted)."""
    return f"{getpass.getuser()}@{platform.node()}"


def canonical(entry: Entry) -> bytes:
    """RFC 8785 canonical JSON bytes."""
    return bytes(rfc8785.dumps(entry))


@dataclass
class CustodyLog:
    """The custody log of one open case."""

    path: Path
    key: bytes
    case_id: str
    actor: str
    head: str = GENESIS
    next_seq: int = 0

    def _aad(self, seq: int) -> bytes:
        return f"ridge-custody-v1|{self.case_id}|{seq}".encode()

    def load(self) -> list[Entry]:
        """Decrypt and verify the whole chain; sets the head for further appends."""
        entries = list(self._decrypt_all())
        self.head, self.next_seq = GENESIS, 0
        for entry in entries:
            if entry.get("seq") != self.next_seq:
                raise IntegrityError(f"custody log: expected entry {self.next_seq}, found {entry.get('seq')}")
            if entry.get("prev") != self.head:
                raise IntegrityError(f"custody log: entry {self.next_seq} does not link to the previous entry")
            self.head = sha256_hex(canonical(entry))
            self.next_seq += 1
        return entries

    def _decrypt_all(self) -> Iterator[Entry]:
        if not self.path.exists():
            return
        with self.path.open("rb") as fh:
            for seq, line in enumerate(fh):
                try:
                    plain = open_sealed(self.key, base64.b64decode(line.strip(), validate=True), self._aad(seq))
                    entry = parse_entry(plain)
                except (IntegrityError, ValueError):  # binascii.Error, JSON and UTF-8 errors are ValueErrors
                    raise IntegrityError(f"custody log: entry {seq} was altered, reordered or removed") from None
                yield entry

    def append(self, action: str, *, result: str = "ok", **fields: Any) -> Entry:
        """Append one entry (fsynced) and advance the head."""
        entry: Entry = {
            "seq": self.next_seq,
            "prev": self.head,
            "ts_utc": utc_now(),
            "actor": self.actor,
            "action": action,
            "result": result,
            **{k: v for k, v in fields.items() if v is not None},
        }
        line = base64.b64encode(seal(self.key, canonical(entry), self._aad(self.next_seq))) + b"\n"
        with self.path.open("ab") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        self.head = sha256_hex(canonical(entry))
        self.next_seq += 1
        return entry

    def sign_head(self, signer: Signer) -> Entry:
        """Append a ``chain.sign`` entry signing the current head."""
        head = self.head
        signature = signer.sign(bytes.fromhex(head))
        return self.append(
            "chain.sign", head=head, key_id=signer.key_id, signature=base64.b64encode(signature).decode("ascii")
        )


def parse_entry(data: bytes) -> Entry:
    """Parse one decrypted entry (its canonical form is re-derived when hashing)."""
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise IntegrityError("custody log: entry is not a JSON object")
    return value


def verify_signed_heads(entries: list[Entry], public_keys: dict[str, bytes]) -> int:
    """Check every chain.sign entry against the hash of the entry before it; returns how many."""
    signed = 0
    for i, entry in enumerate(entries):
        if entry.get("action") != "chain.sign":
            continue
        expected_head = sha256_hex(canonical(entries[i - 1])) if i > 0 else GENESIS
        if entry.get("head") != expected_head:
            raise IntegrityError(f"custody log: signed head in entry {i} does not match the chain")
        public = public_keys.get(str(entry.get("key_id")))
        if public is None:
            raise IntegrityError(f"custody log: entry {i} is signed by unknown key {entry.get('key_id')}")
        signature = base64.b64decode(str(entry.get("signature")), validate=True)
        if not verify_signature(public, signature, bytes.fromhex(expected_head)):
            raise IntegrityError(f"custody log: signature in entry {i} is invalid")
        signed += 1
    return signed
