"""Sidecar session state and the helpers every method module shares.

At most one case is unlocked per sidecar process. The session locks it again after
`idle_timeout_s` without requests, at the end of input and on every new unlock.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ridge.case.case_model import StoredItem
from ridge.case.identity import Signer
from ridge.case.keys import KdfParams, KeyringKeyStore, KeyStore
from ridge.case.store import OpenCase
from ridge.errors import CaseError, ParameterError
from ridge.sidecar.protocol import Json

DEFAULT_IDLE_TIMEOUT_S = 15 * 60.0


@dataclass
class Session:
    """At most one unlocked case per sidecar process, locked again after `idle_timeout_s`."""

    keystore_factory: Callable[[], KeyStore] = KeyringKeyStore
    kdf_params: KdfParams = field(default_factory=KdfParams)  # Argon2id cost for new identities and cases
    idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S
    clock: Callable[[], float] = time.monotonic
    case: OpenCase | None = None
    signer: Signer | None = None
    store: Path | None = None
    last_activity: float = 0.0

    def touch(self) -> None:
        """Lock first if the session sat idle too long, then record activity."""
        now = self.clock()
        if self.case is not None and now - self.last_activity > self.idle_timeout_s:
            self.close()  # an unattended workstation must not keep a decrypted case open
        self.last_activity = now

    def require(self) -> tuple[OpenCase, Signer]:
        """Return the unlocked case and identity, or refuse."""
        if self.case is None or self.signer is None:
            raise CaseError("no case is unlocked")
        return self.case, self.signer

    def require_store(self) -> Path:
        """Return the store of the unlocked case."""
        if self.store is None:  # pragma: no cover - set together with the case
            raise CaseError("no store")
        return self.store

    def close(self) -> None:
        """Lock the case (releases the case lock); forget the signing key."""
        if self.case is not None:
            self.case.close()
        self.case, self.signer, self.store = None, None, None


def absolute(value: str, what: str) -> Path:
    """Return an absolute path from the Rust core (chosen in a native dialog), or refuse."""
    path = Path(value)
    if not path.is_absolute() or "\0" in value:
        raise ParameterError(f"{what} must be an absolute path")
    return path


def item_json(i: StoredItem) -> dict[str, Json]:
    """JSON form of a stored item."""
    return {
        "sha256": i.sha256,
        "role": i.role,
        "size": i.size,
        "label": i.label,
        "job_id": i.job_id,
        "source": i.source,
    }
