"""Store-level ``ridge-case`` commands: verify every case of a store with one passphrase."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.store_verify import verify_store


def cmd_verify_store(args: argparse.Namespace) -> int:
    """Verify every active case of a store; exit 1 when any case failed or cannot be read."""
    results = verify_store(args.store, common.read_passphrase(), common.KEYSTORE_FACTORY())
    for r in results:
        status = "ok" if r.ok and r.checked else ("not checked" if r.ok else "FAILED")
        detail = f"{r.reference}: items {r.items}, reports {r.reports}" if r.checked and r.ok else "; ".join(r.problems)
        common.say(f"{status:11} {r.case_id}  {detail}")
    checked = [r for r in results if r.checked]
    passed = [r for r in checked if r.ok]
    faults = [r for r in results if not r.ok]
    common.say(f"{len(passed)} of {len(checked)} cases verified; {len(faults)} problem(s)")
    return 1 if faults else 0


def add_commands(sub: Any) -> None:
    """Register the store commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("verify-store", help="verify every case of a store (hashes, custody chains, signatures)")
    p.add_argument("--store", type=Path, required=True)
    p.set_defaults(func=cmd_verify_store)
