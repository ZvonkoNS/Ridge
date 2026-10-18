"""Backups of a case store: a byte copy of the encrypted files with a hash manifest (ISO/IEC 27037).

``ridge-case backup --store STORE --to NEW_FOLDER`` copies every regular file of the store into a
folder that must not exist yet and writes ``BACKUP-MANIFEST.json`` (``ridge.store-backup/1``)
with each file's SHA-256 and size. Nothing is decrypted, so no passphrase is needed and IT can run
it. A store with a case open elsewhere (``LOCK``) or a disposal in progress is refused, and every
other case is locked for the copy, so no Ridge window can change it meanwhile.
``ridge-case check-backup FOLDER`` recomputes every hash and refuses added, missing or changed
files.

The manifest is not signed: it detects corruption of the copy. Tampering with case contents is
caught inside each case by its custody chain, signatures and ``ridge-case verify``. A backup holds
the encrypted store only; the examiner's OS-keystore device secret is not in it, so restoring a
store on another account or machine needs that secret too (architecture §9.3).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ridge.case.custody import utc_now
from ridge.case.identity import IDENTITY_FILE
from ridge.case.listing import list_cases
from ridge.case.store import LOCK_FILE
from ridge.errors import IntegrityError, OutputExistsError, ParameterError
from ridge.image_io import publish, read_bounded

SCHEMA = "ridge.store-backup/1"
MANIFEST = "BACKUP-MANIFEST.json"
CHUNK = 1024 * 1024  # files are copied and hashed in chunks, never read whole
MAX_MANIFEST_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class BackupCheck:
    """A backup whose every file matched its manifest."""

    files: int
    bytes: int
    created_utc: str


def _store_files(store: Path) -> list[str]:
    """Every regular file of the store, relative and POSIX-style; links and temporary files refused or skipped."""
    names = []
    for path in sorted(store.rglob("*")):
        if path.is_symlink():
            raise ParameterError(f"the store contains a link ({path.relative_to(store)}); it is not backed up")
        if path.is_file() and not path.name.startswith("."):  # ".name.tmp" files are unfinished writes
            names.append(path.relative_to(store).as_posix())
    return names


def _copy(source: Path, target: Path) -> tuple[str, int]:
    """Copy in chunks to a file that must not exist yet (exclusive create), hashing what was read."""
    digest, size = hashlib.sha256(), 0
    with source.open("rb") as src, target.open("xb") as dst:
        while chunk := src.read(CHUNK):
            digest.update(chunk)
            dst.write(chunk)
            size += len(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    return digest.hexdigest(), size


def _hash(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _lock_cases(store: Path) -> list[Path]:
    """Take every active case's lock so no Ridge window can open one during the copy; refuse when busy."""
    held: list[Path] = []
    for case in list_cases(store):
        if case.state in ("locked", "erasing"):
            _release(held)
            raise ParameterError(f"case {case.case_id[:8]} is open or being disposed; close it first")
        if case.state != "active":
            continue
        lock = store / case.case_id / LOCK_FILE
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:  # opened between the listing and now
            _release(held)
            raise ParameterError(f"case {case.case_id[:8]} was just opened; close it first") from None
        os.write(fd, f"backup {os.getpid()} {utc_now()}".encode())
        os.close(fd)
        held.append(lock)
    return held


def _release(locks: list[Path]) -> None:
    for lock in locks:
        lock.unlink(missing_ok=True)


def backup_store(store: Path, dest: Path) -> dict[str, Any]:
    """Copy the encrypted store to `dest` (which must not exist) with a hash manifest; return the manifest.

    Every active case is locked for the copy (its LOCK file is not copied) and released afterwards.
    """
    if not (store / IDENTITY_FILE).is_file():  # never copy an arbitrary folder chosen by mistake
        raise ParameterError(f"{store} is not a Ridge case store (no {IDENTITY_FILE})")
    if dest.exists():
        raise OutputExistsError(f"{dest.name} already exists: choose a new folder for the backup")
    held = _lock_cases(store)
    try:
        try:
            dest.mkdir()
        except FileExistsError:
            raise OutputExistsError(f"{dest.name} already exists: choose a new folder for the backup") from None
        files = []
        for name in _store_files(store):
            if Path(name).name == LOCK_FILE:
                continue  # our own locks, held for the copy
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            digest, size = _copy(store / name, dest / name)
            files.append({"path": name, "sha256": digest, "size": size})
    finally:
        _release(held)
    manifest = {"schema": SCHEMA, "created_utc": utc_now(), "files": files}
    publish(dest / MANIFEST, json.dumps(manifest, indent=2).encode("utf-8"))
    return manifest


def check_backup(folder: Path) -> BackupCheck:
    """Recompute every file's hash; refuse missing, added or changed files (IntegrityError)."""
    try:
        manifest = json.loads(read_bounded(folder / MANIFEST, MAX_MANIFEST_BYTES).decode("utf-8"))
        listed = {f["path"]: f for f in manifest["files"]}
    except (OSError, ValueError, TypeError, KeyError):
        raise IntegrityError(f"{folder.name} has no readable {MANIFEST}: not a Ridge store backup") from None
    if manifest.get("schema") != SCHEMA:
        raise IntegrityError(f"not a {SCHEMA} backup")
    for name in listed:
        if not isinstance(name, str) or name.startswith(("/", "\\")) or ".." in Path(name).parts or ":" in name:
            raise IntegrityError(f"the manifest names an unsafe path: {name!r}")
    present = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() or p.is_symlink()}
    present.discard(MANIFEST)
    if present != set(listed):
        raise IntegrityError(
            f"files added {sorted(present - set(listed))} or missing {sorted(set(listed) - present)} since the backup"
        )
    total = 0
    for name, entry in listed.items():
        path = folder / name
        if path.is_symlink():
            raise IntegrityError(f"{name} is a link")
        digest, size = _hash(path)
        if digest != entry.get("sha256") or size != entry.get("size"):
            raise IntegrityError(f"{name} changed since the backup")
        total += size
    return BackupCheck(len(listed), total, str(manifest.get("created_utc", "")))
