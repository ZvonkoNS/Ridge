"""Sidecar methods for the device-secret recovery file (ADR-012), sent by the Rust core only.

The passphrases arrive from the Rust prompt window, never from the WebView. Results name the key,
the secret's fingerprint and the file, never the secret.
"""

from __future__ import annotations

from dataclasses import asdict

from ridge.case.recovery import RecoveryFile, export_recovery, import_recovery, open_recovery
from ridge.sidecar.protocol import Json
from ridge.sidecar.session import Session, absolute


def _shown(info: RecoveryFile, path: str) -> Json:
    return {**asdict(info), "file": path}


def export(session: Session, params: dict[str, Json]) -> Json:
    """Seal this account's device secret into a new file (logged in the store audit file)."""
    store, dest = absolute(params["store"], "store"), absolute(params["dest"], "dest")
    keystore = session.keystore_factory()
    info = export_recovery(store, params["examiner_passphrase"], params["recovery_passphrase"], keystore, dest)
    return _shown(info, params["dest"])


def check_passphrase(session: Session, params: dict[str, Json]) -> Json:
    """Open a recovery file with its passphrase and say what it holds; nothing is written."""
    info, _ = open_recovery(absolute(params["path"], "path"), params["recovery_passphrase"])
    return _shown(info, params["path"])


def restore(session: Session, params: dict[str, Json]) -> Json:
    """Restore the device secret into this account's keystore after proving it opens the store."""
    path, store = absolute(params["path"], "path"), absolute(params["store"], "store")
    info = import_recovery(
        path, params["recovery_passphrase"], store, params["examiner_passphrase"], session.keystore_factory()
    )
    return _shown(info, params["path"])
