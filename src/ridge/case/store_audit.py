"""Store audit file: store-level actions that no case can log, because none is open (ADR-012).

``<store>/store-audit.jsonl`` holds one JSON object per line. Each entry names the SHA-256 of
the previous one (``prev``) and its own hash over its canonical form (RFC 8785, without
``hash``), so an edited, removed or reordered entry breaks the chain. Every read verifies the
whole chain; a broken chain is an IntegrityError, never silently repaired.

A chain alone cannot show that its last entries, or the whole file, were removed. So every
append also records the head (sequence number and hash) in this account's OS keystore, next to
the device secret, and a read with the keystore checks the file still reaches that head. An
account that has never written to the store (for example a new account before its first
restore) has no anchor yet, and only the chain is checked.

Appends are serialised across processes by an OS lock on ``store-audit.lock``, released by the
OS if a process ends. Entries hold hashes, fingerprints, paths and the OS account name: no
evidence and no secrets.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import rfc8785

from ridge.case.crypto import sha256_hex
from ridge.case.custody import default_actor, utc_now
from ridge.case.identity import IDENTITY_FILE, public_identity
from ridge.case.keys import KeyStore
from ridge.errors import CaseLockedError, InputRejectedError, IntegrityError
from ridge.image_io import read_bounded

FILE = "store-audit.jsonl"
LOCK_FILE = "store-audit.lock"
GENESIS = "0" * 64
MAX_BYTES = 16 * 1024 * 1024
LOCK_TIMEOUT_S = 10.0
ANCHOR_PREFIX = "store-audit-head-"  # keystore entry per store identity: {"seq", "hash"} of the last entry
type AuditEntry = dict[str, Any]


def _hash(entry: AuditEntry) -> str:
    return sha256_hex(bytes(rfc8785.dumps({k: v for k, v in entry.items() if k != "hash"})))


def _chain(store: Path) -> list[AuditEntry]:
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


def _anchor_name(store: Path) -> str | None:
    if not (store / IDENTITY_FILE).is_file():
        return None
    return ANCHOR_PREFIX + public_identity(store)[0]


def _check_anchor(store: Path, keystore: KeyStore, entries: list[AuditEntry]) -> None:
    name = _anchor_name(store)
    raw = keystore.get(name) if name else None
    if raw is None:
        return  # this account has not written to this store's audit file yet
    try:
        anchor = json.loads(raw.decode("utf-8"))
        seq, head = anchor["seq"], anchor["hash"]
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError):
        raise IntegrityError("this account's record of the store audit head is malformed") from None
    if not isinstance(seq, int) or seq >= len(entries):
        raise IntegrityError(f"{FILE}: entries were removed (this account last wrote entry {seq})")
    if entries[seq].get("hash") != head:
        raise IntegrityError(f"{FILE}: entry {seq} was replaced since this account wrote it")


def read_audit(store: Path, keystore: KeyStore | None = None) -> list[AuditEntry]:
    """Every entry, oldest first, after checking the chain and, with `keystore`, this account's head."""
    entries = _chain(store)
    if keystore is not None:
        _check_anchor(store, keystore, entries)
    return entries


def append_audit(store: Path, keystore: KeyStore, action: str, **fields: Any) -> AuditEntry:
    """Under the store-audit lock: verify, append one entry, flush it, and record the new head."""
    with _locked(store):
        entries = read_audit(store, keystore)
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
        name = _anchor_name(store)
        if name is not None:
            keystore.set(name, json.dumps({"seq": entry["seq"], "hash": entry["hash"]}).encode("utf-8"))
    return entry


@contextmanager
def _locked(store: Path) -> Iterator[None]:
    with (store / LOCK_FILE).open("a+b") as fh:
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while not _try_lock(fh.fileno()):
            if time.monotonic() > deadline:
                raise CaseLockedError("another Ridge process is writing the store audit file; try again")
            time.sleep(0.05)
        try:
            yield
        finally:
            _unlock(fh.fileno())


if sys.platform == "win32":
    import msvcrt

    def _try_lock(fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
