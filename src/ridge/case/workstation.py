"""Workstation check: how this installation and its store are set up, before casework starts.

Read-only. Nothing is created, decrypted or logged, and the device secret is only looked up, never
shown. The check reports facts and points the examiner or the laboratory at what to fix. It is not a
validation of the method or of the installation: per-architecture reproducibility (NFR-3) is shown by
the characterization tests, and method validation is the laboratory's (OQ-6, OQ-15).
"""

from __future__ import annotations

import os
import platform
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ridge.case.crypto import KEY_LEN
from ridge.case.identity import IDENTITY_FILE, public_identity
from ridge.case.jobs import environment
from ridge.case.key_register import confirm_key, describe, load_register
from ridge.case.keys import DEVICE_SECRET_NAME, KeyStore
from ridge.case.limits import load_limits
from ridge.case.listing import list_cases
from ridge.errors import QualityToolError, RidgeError
from ridge.image_io import HEIF_AVAILABLE
from ridge.quality.nfiq2 import Nfiq2

REFERENCE_ARCHITECTURES = ("x86_64", "arm64")  # those with stored reference results (tests/golden)
_ARCH_FAMILY = {"amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}


@dataclass(frozen=True)
class Finding:
    """One line of the check: a topic, how it stands ("ok", "note" or "problem") and plain words."""

    topic: str
    level: str
    text: str

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form."""
        return asdict(self)


def check_workstation(
    store: Path, keystore: KeyStore, register: Path | None = None, nfiq2: Sequence[str] | None = None
) -> list[Finding]:
    """Check the software, the OS keystore, the store and its limits; if given, the key register and NFIQ 2."""
    found = [*_software(), _keystore(keystore, has_identity=(store / IDENTITY_FILE).is_file()), *_store(store)]
    found.extend(_limits(store))
    if register is not None:
        found.append(_register(store, register))
    if nfiq2 is not None:
        found.append(_nfiq2(nfiq2))
    return found


def _software() -> list[Finding]:
    env = environment()
    commit, source = env["commit"], env["commit_source"]
    if source == "unknown":
        ridge = Finding("Ridge", "note", f"Ridge {env['version']}; the source commit is unknown and reports say so")
    else:
        ridge = Finding("Ridge", "ok", f"Ridge {env['version']}, commit {commit[:12]} ({source})")
    family = _ARCH_FAMILY.get(env["machine"].lower(), env["machine"])
    where = f"{env['platform']}, {env['machine']}, Python {env['python']}"
    if family in REFERENCE_ARCHITECTURES:
        arch = Finding("Platform", "ok", f"{where}. Results are reproducible per architecture ({family})")
    else:
        arch = Finding("Platform", "note", f"{where}. Ridge has no reference results for this architecture")
    libraries = ", ".join(f"{name} {version}" for name, version in env["dependencies"].items())
    heif = "HEIF/HEIC photos can be read" if HEIF_AVAILABLE else "HEIF/HEIC photos cannot be read (ridge[heic])"
    return [ridge, arch, Finding("Libraries", "ok", f"{libraries}. {heif}")]


def _keystore(keystore: KeyStore, *, has_identity: bool) -> Finding:
    try:
        secret = keystore.get(DEVICE_SECRET_NAME)
    except Exception as exc:  # noqa: BLE001 - any keystore back-end failure is reported, not raised
        return Finding("OS keystore", "problem", f"the OS keystore cannot be read ({type(exc).__name__})")
    if secret is None:
        if has_identity:
            text = "this account's OS keystore has no Ridge device secret: this store's cases cannot be opened here"
            return Finding("OS keystore", "problem", text)
        return Finding("OS keystore", "note", "no Ridge device secret yet; it is created with the examiner identity")
    if len(secret) != KEY_LEN:
        return Finding("OS keystore", "problem", "the Ridge device secret in the OS keystore is malformed")
    text = "the Ridge device secret is present (not shown). Store backups do not carry it (ADR-012)"
    return Finding("OS keystore", "ok", text)


def _store(store: Path) -> list[Finding]:
    try:
        cases = list_cases(store)
    except RidgeError as exc:
        return [Finding("Store", "problem", str(exc))]
    found: list[Finding] = []
    if (store / IDENTITY_FILE).is_file():
        try:
            key_id, _ = public_identity(store)
        except RidgeError as exc:
            found.append(Finding("Identity", "problem", str(exc)))
        else:
            found.append(Finding("Identity", "ok", f"examiner signing key {key_id}"))
    else:
        found.append(Finding("Identity", "note", "no examiner identity yet; create one before the first case"))
    states = Counter(case.state for case in cases)
    counts = ", ".join(f"{n} {state}" for state, n in sorted(states.items())) or "no cases"
    if not os.access(store, os.W_OK):
        found.append(Finding("Store", "problem", f"{store} cannot be written by this account ({counts})"))
    elif states["erasing"] or states["invalid"]:
        text = f"{counts}: an interrupted disposal or an unreadable case folder needs attention"
        found.append(Finding("Store", "problem", text))
    else:
        found.append(Finding("Store", "ok", f"{store} ({counts})"))
    return found


def _limits(store: Path) -> list[Finding]:
    try:
        limits = load_limits(store)
    except RidgeError as exc:
        return [Finding("Limits of use", "problem", str(exc))]
    if limits is None:
        return [Finding("Limits of use", "note", "none configured: jobs are not checked against laboratory limits")]
    signer = f"signed by {limits.signed_by['key_id']}" if limits.signed_by else "not signed"
    stated = Finding("Limits of use", "ok" if limits.signed_by else "note", f"{limits.source}, {signer}")
    found = [stated]
    machine = platform.machine()
    if limits.architectures and machine not in limits.architectures:
        covered = ", ".join(limits.architectures)
        text = f"this workstation's CPU architecture ({machine}) is not among those the limits cover ({covered})"
        found.append(Finding("Limits of use", "problem", text))
    if limits.min_nfiq2 is not None:
        text = f"a minimum NFIQ 2 score of {limits.min_nfiq2:g} is set: jobs without the NFIQ 2 tool record a deviation"
        found.append(Finding("Limits of use", "note", text))
    return found


def _nfiq2(command: Sequence[str]) -> Finding:
    """Whether the configured NFIQ 2 tool is there and reports its version (it is asked nothing else)."""
    try:
        tool = Nfiq2(command, work_dir=Path(tempfile.gettempdir()))  # no image is written for a version query
    except RidgeError as exc:
        return Finding("NFIQ 2", "problem", str(exc))
    try:
        exit_code, version = tool.ask_version()
    except QualityToolError as exc:  # missing, cannot start, timed out or printed too much
        return Finding("NFIQ 2", "problem", f"{exc}: jobs cannot compute NFIQ 2 scores")
    if exit_code != 0:
        text = f"the tool exited with code {exit_code} when asked for its version: check the path and arguments"
        return Finding("NFIQ 2", "problem", text)
    if version is None:
        return Finding("NFIQ 2", "note", "the tool ran but reported no version; its scores are indicative only")
    return Finding("NFIQ 2", "ok", f"{version}; its scores are indicative only (photos are outside NFIQ 2's scope)")


def _register(store: Path, register: Path) -> Finding:
    try:
        key_id, _ = public_identity(store)
        known = load_register(register)
        key = confirm_key(known, key_id, "examiner", datetime.now(UTC).isoformat())
    except RidgeError as exc:
        return Finding("Key register", "problem", str(exc))
    return Finding("Key register", "ok", describe(known, key))
