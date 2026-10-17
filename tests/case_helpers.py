"""Helpers for case-store tests: in-memory keystore, fast-but-valid KDF cost, ready-made cases."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from ridge.case.keys import KdfParams
from ridge.case.store import create_case
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME

PASSPHRASE = "correct horse battery staple 42"  # noqa: S105  # synthetic test passphrase
FAST_KDF = KdfParams(time_cost=3, memory_kib=64 * 1024, parallelism=1)  # the minimum the code accepts
ACTOR = "examiner@workstation"


class MemoryKeyStore:
    """KeyStore that keeps secrets in memory (tests never touch the real OS keystore)."""

    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    def get(self, name: str) -> bytes | None:
        return self.values.get(name)

    def set(self, name: str, value: bytes) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


def future(days: int = 30) -> date:
    return datetime.now(UTC).date() + timedelta(days=days)


def new_case(store: Path, keystore: MemoryKeyStore, *, reference: str = "KT-2026-0001") -> Path:
    return create_case(
        store,
        case_reference=reference,
        legal_basis="Synthetic test basis",
        retention_until=future(),
        passphrase=PASSPHRASE,
        keystore=keystore,
        params=FAST_KDF,
        actor=ACTOR,
    )


def photo_file(folder: Path, name: str = "whorl_default", filename: str = "finger.png") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    return write_png(folder / filename, CASES_BY_NAME[name].photo())
