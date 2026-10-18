"""Sidecar methods for the store and the session: listing, first run, unlock and lock.

``identity.create``, ``case.create`` and ``session.unlock`` carry the examiner passphrase and must
only ever be sent by the Rust core from its passphrase prompt, never from WebView code.
"""

from __future__ import annotations

import uuid
from datetime import date

import ridge
from ridge.case.file_check import check_exported
from ridge.case.identity import IDENTITY_FILE, create_identity, public_identity, unlock_identity
from ridge.case.key_card import write_card
from ridge.case.keys import b64
from ridge.case.limits import load_limits
from ridge.case.listing import list_cases
from ridge.case.store import create_case, open_case
from ridge.case.store_overview import store_overview
from ridge.case.store_verify import verify_store
from ridge.errors import ParameterError
from ridge.sidecar.protocol import Json
from ridge.sidecar.session import Session, absolute

PROTOCOL = "ridge.sidecar/1"


def version(session: Session, params: dict[str, Json]) -> Json:
    """Ridge and protocol versions."""
    return {"ridge": ridge.__version__, "protocol": PROTOCOL}


def cases(session: Session, params: dict[str, Json]) -> Json:
    """Cases of a store for the open dialog: ids, creation time and state only (nothing decrypted)."""
    return [case.to_json() for case in list_cases(absolute(params["store"], "store"))]


def identity_status(session: Session, params: dict[str, Json]) -> Json:
    """Whether a store has an examiner identity, and its public part (nothing is unlocked).

    The GUI uses this to choose between the first-run flow and the case list, and to show the key
    id the examiner registers with the lab (architecture §9.3).
    """
    store = absolute(params["store"], "store")
    if not (store / IDENTITY_FILE).is_file():
        return {"exists": False}
    key_id, public = public_identity(store)  # refuses a malformed or inconsistent identity file
    return {"exists": True, "key_id": key_id, "public_key": b64(public)}


def limits_of_use(session: Session, params: dict[str, Json]) -> Json:
    """Return the store's limits of use (PRD §12 item 8): source, file hash, limits; nothing is decrypted.

    A malformed limits file, or a signature that does not verify, is refused here as it is by every
    job, so the examiner sees it at once.
    """
    limits = load_limits(absolute(params["store"], "store"))
    if limits is None:
        return {"configured": False}
    return {
        "configured": True,
        "source": limits.source,
        "sha256": limits.sha256,
        "limits": limits.to_json(),
        "signed_by": limits.signed_by,
    }


def verify_all(session: Session, params: dict[str, Json]) -> Json:
    """Verify every case of a store with the examiner passphrase (sent by the Rust core only).

    The open case, if any, is locked first: a store check never runs beside an unlocked case.
    """
    session.close()
    store = absolute(params["store"], "store")
    return [check.to_json() for check in verify_store(store, params["passphrase"], session.keystore_factory())]


def overview(session: Session, params: dict[str, Json]) -> Json:
    """Every case's reference, retention and hold, read with the passphrase (sent by the Rust core only).

    Nothing is written; the open case, if any, is locked first.
    """
    session.close()
    store = absolute(params["store"], "store")
    return [case.to_json() for case in store_overview(store, params["passphrase"], session.keystore_factory())]


def identity_create(session: Session, params: dict[str, Json]) -> Json:
    """Create the examiner signing identity of a store (first run; sent by the Rust core only)."""
    store = absolute(params["store"], "store")
    signer = create_identity(store, params["passphrase"], session.keystore_factory(), session.kdf_params)
    return {"key_id": signer.key_id, "public_key": b64(signer.public_key)}


def files_check(session: Session, params: dict[str, Json]) -> Json:
    """Verify an exported file or package folder chosen in a native dialog (no store; nothing written)."""
    register = params.get("register")
    path = absolute(params["path"], "path")
    return check_exported(path, absolute(register, "register") if register else None).to_json()


def identity_card(session: Session, params: dict[str, Json]) -> Json:
    """Write a self-signed key card for the laboratory's register (sent by the Rust core only)."""
    store = absolute(params["store"], "store")
    signer = unlock_identity(store, params["passphrase"], session.keystore_factory())
    card = write_card(signer, "examiner", params["holder"], absolute(params["dest"], "dest"))
    return {"key_id": card.key_id, "holder": card.holder, "exported": params["dest"]}


def case_create(session: Session, params: dict[str, Json]) -> Json:
    """Create a case protected by the identity's passphrase (sent by the Rust core only); unlock it next."""
    store = absolute(params["store"], "store")
    try:
        retention = date.fromisoformat(params["retention_until"])
    except ValueError:
        raise ParameterError("retention_until must be a date, YYYY-MM-DD") from None
    keystore = session.keystore_factory()
    unlock_identity(store, params["passphrase"], keystore)  # one passphrase for identity and cases
    case_dir = create_case(
        store,
        case_reference=params["reference"],
        legal_basis=params["legal_basis"],
        retention_until=retention,
        passphrase=params["passphrase"],
        keystore=keystore,
        params=session.kdf_params,
    )
    return {"case_id": case_dir.name}


def unlock(session: Session, params: dict[str, Json]) -> Json:
    """Open one case of a store with the examiner passphrase (sent by the Rust core only)."""
    store = absolute(params["store"], "store")
    try:
        case_id = str(uuid.UUID(params["case_id"]))
    except ValueError:
        raise ParameterError("case_id must be a case UUID") from None
    session.close()
    keystore = session.keystore_factory()
    signer = unlock_identity(store, params["passphrase"], keystore)
    case = open_case(store / case_id, params["passphrase"], keystore)
    try:
        meta = case.meta()
    except BaseException:
        case.close()  # a case whose metadata cannot be read is never left unlocked (fail closed)
        raise
    session.case, session.signer, session.store = case, signer, store
    return {
        "case_id": case_id,
        "reference": meta.case_reference,
        "retention_until": meta.retention_until.isoformat(),
        "legal_hold": meta.legal_hold,
    }


def status(session: Session, params: dict[str, Json]) -> Json:
    """Whether a case is unlocked, and the idle timeout."""
    return {"unlocked": session.case is not None, "idle_timeout_s": session.idle_timeout_s}


def lock(session: Session, params: dict[str, Json]) -> Json:
    """Lock the open case."""
    session.close()
    return {"locked": True}
