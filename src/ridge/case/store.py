"""Encrypted per-case store (PRD FR-20 to FR-26, architecture §8, ADR-004/005/008).

Layout of ``<store>/<case_id>/``::

    case.json              schema, case id, KDF parameters, salt, wrapped data key (no personal data)
    meta.enc               case reference, legal basis, retention date, legal hold (encrypted)
    evidence/<name>.enc    original evidence, never rewritten
    artefacts/<name>.enc   derived outputs
    reports/<job>.json.enc + .sig   signed job reports
    custody.jsonl.enc      hash-chained custody log (the index of everything above)
    LOCK                   present while the case is open (single writer)

``<name>`` is HMAC-SHA256 of the plaintext SHA-256 under a key derived from the case data key.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from ridge.case.case_model import (
    CASE_FILE,
    ERASING_SCHEMA,
    IMPORT_ACTIONS,
    ITEM_ACTIONS,
    LOCK_FILE,
    META_FILE,
    ROLES,
    SCHEMA,
    CaseMeta,
    StoredItem,
    clean_text,
    path_label,
    publish_logged,
)
from ridge.case.crypto import derive_subkey, keyed_name, open_sealed, random_key, seal, sha256_hex
from ridge.case.custody import CustodyLog, Entry, default_actor, utc_now
from ridge.case.keys import SALT_LEN, KdfParams, KeyStore, b64, check_passphrase, derive_kek, device_secret, unb64
from ridge.errors import CaseError, CaseLockedError, InputRejectedError, IntegrityError, KeyCustodyError, ParameterError
from ridge.image_io import ReadLimits, decode_image, publish, read_bounded

MAX_CASE_FILE_BYTES = 64 * 1024  # case.json is well under 1 KiB


def create_case(
    store: Path,
    *,
    case_reference: str,
    legal_basis: str,
    retention_until: date,
    passphrase: str,
    keystore: KeyStore,
    params: KdfParams | None = None,
    actor: str | None = None,
) -> Path:
    """Create a new encrypted case and return its folder. Refuses missing reference, basis or retention."""
    meta = CaseMeta(
        clean_text(case_reference, "case reference"), clean_text(legal_basis, "legal basis", 500), retention_until
    )
    if retention_until <= datetime.now(UTC).date():
        raise ParameterError("the retention date must be in the future")
    check_passphrase(passphrase)
    params = params or KdfParams()
    case_id = str(uuid.uuid4())
    case_dir = store / case_id
    case_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    dek, salt = random_key(), secrets.token_bytes(SALT_LEN)
    kek = derive_kek(passphrase, salt, params, device_secret(keystore, create=True), b"case|" + case_id.encode())
    record = {
        "schema": SCHEMA,
        "case_id": case_id,
        "created_utc": utc_now(),
        "kdf": params.to_json(),
        "salt": b64(salt),
        "wrapped_dek": b64(seal(kek, dek, _dek_aad(case_id))),
    }
    publish(case_dir / CASE_FILE, json.dumps(record, indent=2).encode("utf-8"))
    with OpenCase(case_dir, dek, actor or default_actor()) as case:
        case.write_meta(meta)
        case.custody.append("case.create", retention_until=meta.retention_until.isoformat())
    return case_dir


def open_case(case_dir: Path, passphrase: str, keystore: KeyStore, actor: str | None = None) -> OpenCase:
    """Unlock a case. Use as a context manager so the lock is always released."""
    record = read_case_record(case_dir)
    case_id = record["case_id"]
    try:
        salt, wrapped = unb64(record["salt"]), unb64(record["wrapped_dek"])
    except (KeyError, TypeError, ValueError, AttributeError):  # binascii.Error is a ValueError
        raise IntegrityError(f"{CASE_FILE} is malformed") from None
    secret = device_secret(keystore, create=False)
    kek = derive_kek(passphrase, salt, KdfParams.from_json(record["kdf"]), secret, b"case|" + case_id.encode())
    try:
        dek = open_sealed(kek, wrapped, _dek_aad(case_id))
    except IntegrityError:
        raise KeyCustodyError("cannot unlock the case: wrong passphrase or wrong OS account") from None
    return OpenCase(case_dir, dek, actor or default_actor())


def read_case_record(case_dir: Path) -> dict[str, Any]:
    """Read the plaintext case.json (it holds no secrets in clear)."""
    path = case_dir / CASE_FILE
    if not path.is_file():
        raise CaseError(f"{case_dir} is not a Ridge case (no {CASE_FILE})")
    try:
        record = json.loads(read_bounded(path, MAX_CASE_FILE_BYTES).decode("utf-8"))
    except (InputRejectedError, UnicodeDecodeError, json.JSONDecodeError):
        raise IntegrityError(f"{CASE_FILE} is malformed") from None
    if isinstance(record, dict) and record.get("schema") == ERASING_SCHEMA:
        raise CaseError("this case was crypto-erased but its disposal was interrupted: run `ridge-case dispose` again")
    if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("case_id") != case_dir.name:
        raise IntegrityError(f"{CASE_FILE} does not describe this case folder")
    return record


def _dek_aad(case_id: str) -> bytes:
    return f"ridge-dek-v1|{case_id}".encode()


class OpenCase:
    """An unlocked case holding the single-writer lock."""

    def __init__(self, case_dir: Path, dek: bytes, actor: str) -> None:
        self.dir = case_dir
        self.case_id = case_dir.name
        self._data_key = derive_subkey(dek, b"ridge-data-v1")
        self._name_key = derive_subkey(dek, b"ridge-names-v1")
        self._lock = case_dir / LOCK_FILE
        try:
            fd = os.open(self._lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise CaseLockedError(
                f"case {self.case_id} is open elsewhere (if a run crashed, delete {self._lock})"
            ) from None
        os.write(fd, f"{os.getpid()} {utc_now()}".encode())
        os.close(fd)
        self.custody = CustodyLog(
            case_dir / "custody.jsonl.enc", derive_subkey(dek, b"ridge-custody-v1"), self.case_id, actor
        )
        try:
            self.entries: list[Entry] = self.custody.load()
        except BaseException:
            self.close()  # never leave the case locked after a failed open
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release the lock."""
        self._lock.unlink(missing_ok=True)

    # ------------------------------------------------------------------ metadata
    def write_meta(self, meta: CaseMeta) -> None:
        """Replace the encrypted metadata (atomic)."""
        blob = seal(self._data_key, json.dumps(meta.to_json()).encode("utf-8"), self._aad("meta", "meta"))
        publish(self.dir / META_FILE, blob, overwrite=True)

    def meta(self) -> CaseMeta:
        """Decrypt the case metadata."""
        blob = (self.dir / META_FILE).read_bytes()
        return CaseMeta.from_json(json.loads(open_sealed(self._data_key, blob, self._aad("meta", "meta"))))

    def set_legal_hold(self, on: bool, reason: str) -> None:
        """Place or lift a legal hold (logged)."""
        meta = self.meta()
        self.write_meta(CaseMeta(meta.case_reference, meta.legal_basis, meta.retention_until, on))
        # Kept in `entries` too: a long-lived session (the GUI sidecar) verifies and exports from them.
        self.entries.append(self.custody.append("case.hold", legal_hold=on, reason=clean_text(reason, "reason", 500)))

    # ------------------------------------------------------------------ blobs
    def _aad(self, role: str, sha: str) -> bytes:
        return f"ridge-blob-v1|{self.case_id}|{role}|{sha}".encode()

    def blob_path(self, role: str, sha: str) -> Path:
        """Where the encrypted blob for (`role`, `sha`) lives."""
        return self.dir / ROLES[role] / f"{keyed_name(self._name_key, sha)}.enc"

    def items(self) -> list[StoredItem]:
        """Everything stored in the case, from the custody log."""
        found: dict[str, StoredItem] = {}
        for e in self.entries:
            if e["action"] in ITEM_ACTIONS and e["result"] == "ok":
                found[e["sha256"]] = StoredItem(
                    e["sha256"], e["role"], e["size"], e["label"], e.get("job_id"), e.get("source")
                )
        return list(found.values())

    def item(self, sha: str) -> StoredItem:
        """Find the stored item with this SHA-256 (full hex or a unique prefix of at least 8 chars)."""
        matches = [i for i in self.items() if i.sha256 == sha or (len(sha) >= 8 and i.sha256.startswith(sha))]
        if len(matches) != 1:
            raise CaseError(f"no unique stored item matches {sha!r}")
        return matches[0]

    def _put(self, data: bytes, role: str, label: str, job_id: str | None, source: str | None = None) -> StoredItem:
        sha = sha256_hex(data)
        item = StoredItem(sha, role, len(data), clean_text(label, "label", 255), job_id, source)
        action = IMPORT_ACTIONS.get(role, "artefact.write")
        existing = next((i for i in self.items() if i.sha256 == sha), None)
        if existing is not None and existing.role != role and role in IMPORT_ACTIONS:
            raise ParameterError(  # one blob has one role; a reference must not silently resolve to evidence
                f"{path_label(label)} is byte-identical to the stored {existing.role} {sha[:12]}; "
                f"it cannot also be imported as {role}"
            )
        if existing is not None and source is not None and existing.source != source:
            had = f"with the source note {existing.source!r}" if existing.source else "without a source note"
            raise ParameterError(  # provenance is never silently dropped or rewritten
                f"{path_label(label)} is already stored as {existing.role} {sha[:12]} {had}; "
                "a stored item's source note cannot be changed"
            )
        if existing is not None:
            self._log(action, item, result="duplicate")
            return item
        path = self.blob_path(role, sha)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        publish(path, seal(self._data_key, data, self._aad(role, sha)))  # never replaces an existing blob
        self._log(action, item)
        return item

    def _log(self, action: str, item: StoredItem, result: str = "ok") -> None:
        self.entries.append(
            self.custody.append(
                action,
                result=result,
                sha256=item.sha256,
                role=item.role,
                size=item.size,
                label=item.label,
                job_id=item.job_id,
                source=item.source,
            )
        )

    def import_evidence(self, path: Path, limits: ReadLimits | None = None, *, source: str | None = None) -> StoredItem:
        """Copy an original photo into the case: validated, hashed, encrypted; the source is only read.

        `source` is the examiner's note on where the photo came from (exhibit number, device), kept
        encrypted in the custody log and repeated in every job report on this photo.
        """
        limits = limits or ReadLimits()
        data = read_bounded(path, limits.max_bytes)
        decode_image(data, limits)  # refuse anything Ridge could not process later
        return self._put(data, "evidence", path.name, None, clean_text(source, "source") if source else None)

    def import_reference(self, path: Path, source: str, limits: ReadLimits | None = None) -> StoredItem:
        """Import a NAFIS/AFIS candidate image for viewing beside an export (FR-52); hashed and logged like evidence.

        References are never processed: jobs run on evidence only.
        """
        limits = limits or ReadLimits()
        data = read_bounded(path, limits.max_bytes)
        decode_image(data, limits)
        return self._put(data, "reference", path.name, None, clean_text(source, "source"))

    def store_artefact(self, data: bytes, *, role: str, label: str, job_id: str) -> StoredItem:
        """Store a derived output of a job."""
        if role in IMPORT_ACTIONS or role not in ROLES:
            raise ParameterError(f"invalid artefact role {role!r}")
        return self._put(data, role, label, job_id)

    def read(self, sha: str, *, log: bool = True, job_id: str | None = None) -> bytes:
        """Decrypt a stored blob and check its hash (logged as a read unless `log` is False)."""
        item = self.item(sha)
        data = open_sealed(
            self._data_key, self.blob_path(item.role, item.sha256).read_bytes(), self._aad(item.role, item.sha256)
        )
        if sha256_hex(data) != item.sha256:
            raise IntegrityError(f"stored {item.role} {item.sha256[:12]} does not match its hash")
        if log:
            self.entries.append(self.custody.append(f"{item.role}.read", sha256=item.sha256, job_id=job_id))
        return data

    def export(self, sha: str, dest: Path, *, overwrite: bool = False) -> Path:
        """Write one item in plaintext to `dest`: the only way data leaves the store (logged)."""
        item = self.item(sha)
        data = self.read(item.sha256, log=False)
        publish_logged(
            [(dest, data)],
            lambda: self.entries.append(
                self.custody.append(
                    "artefact.export", sha256=item.sha256, role=item.role, destination=str(dest.resolve())
                )
            ),
            overwrite=overwrite,
        )
        return dest

    # ------------------------------------------------------------------ reports
    def report_paths(self, job_id: str) -> tuple[Path, Path]:
        """(sealed report, detached signature) for a job."""
        return self.dir / "reports" / f"{job_id}.json.enc", self.dir / "reports" / f"{job_id}.json.sig"

    def put_report(self, job_id: str, canonical: bytes, signature: bytes) -> None:
        """Store a signed report (canonical JSON) for `job_id`."""
        report_path, sig_path = self.report_paths(job_id)
        report_path.parent.mkdir(mode=0o700, exist_ok=True)
        publish(report_path, seal(self._data_key, canonical, self._aad("report", job_id)))
        publish(sig_path, signature)

    def get_report(self, job_id: str) -> tuple[bytes, bytes]:
        """(canonical report bytes, signature) for `job_id`."""
        report_path, sig_path = self.report_paths(job_id)
        canonical = open_sealed(self._data_key, report_path.read_bytes(), self._aad("report", job_id))
        return canonical, sig_path.read_bytes()
