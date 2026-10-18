"""Store audit file: store-level actions that no case can log, because none is open (ADR-012).

``<store>/store-audit.jsonl`` holds one JSON object per line. Each entry names the SHA-256 of
the previous one (``prev``) and its own hash over its canonical form (RFC 8785, without
``hash``), so an edited, removed or reordered entry breaks the chain. Every read verifies the
whole chain; a broken chain is an IntegrityError, never silently repaired. Entries hold hashes,
fingerprints, paths and the OS account name: no evidence and no secrets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import rfc8785

from ridge.case.crypto import sha256_hex
from ridge.case.custody import default_actor, utc_now
from ridge.errors import InputRejectedError, IntegrityError
from ridge.image_io import read_bounded

FILE = "store-audit.jsonl"
GENESIS = "0" * 64
MAX_BYTES = 16 * 1024 * 1024
type AuditEntry = dict[str, Any]


def _hash(entry: AuditEntry) -> str:
    return sha256_hex(bytes(rfc8785.dumps({k: v for k, v in entry.items() if k != "hash"})))


def read_audit(store: Path) -> list[AuditEntry]:
    """Every entry of the store audit file, oldest first, after checking the whole chain."""
    path = store / FILE
    if not path.exists():
        return []
    try:
        lines = read_bounded(path, MAX_BYTES).decode("utf-8").splitlines()
        entries = [json.loads(line) for line in lines]
    except (InputRejectedError, UnicodeDecodeError, json.JSONDecodeError):
        raise IntegrityError(f"{FILE} is not a readable store audit file") from None
    prev = GENESIS
    for seq, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("seq") != seq or entry.get("prev") != prev:
            raise IntegrityError(f"{FILE}: the chain is broken at entry {seq}")
        if entry.get("hash") != _hash(entry):
            raise IntegrityError(f"{FILE}: entry {seq} was changed")
        prev = entry["hash"]
    return entries


def append_audit(store: Path, action: str, **fields: Any) -> AuditEntry:
    """Verify the chain, then append one entry and flush it to disk."""
    entries = read_audit(store)
    entry: AuditEntry = {
        "seq": len(entries),
        "ts_utc": utc_now(),
        "actor": default_actor(),
        "action": action,
        **fields,
        "prev": entries[-1]["hash"] if entries else GENESIS,
    }
    entry["hash"] = _hash(entry)
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    with (store / FILE).open("ab") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    return entry
