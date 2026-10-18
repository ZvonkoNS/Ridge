"""Store-level ``ridge-case`` commands: verify every case of a store with one passphrase."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.store_overview import store_overview
from ridge.case.store_verify import verify_store


def cmd_verify_store(args: argparse.Namespace) -> int:
    """Verify every active case of a store; exit 1 when any case failed or cannot be read."""
    results = verify_store(args.store, common.read_passphrase(), common.KEYSTORE_FACTORY())
    for r in results:
        status = ("ok" if r.ok else "FAILED") if r.checked else ("not checked" if r.ok else "NOT CHECKED")
        detail = f"{r.reference}: items {r.items}, reports {r.reports}" if r.checked and r.ok else "; ".join(r.problems)
        common.say(f"{status:11} {r.case_id}  {detail}")
    checked = [r for r in results if r.checked]
    passed = [r for r in checked if r.ok]
    faults = [r for r in results if not r.ok]
    common.say(f"{len(passed)} of {len(checked)} cases verified; {len(faults)} problem(s)")
    return 1 if faults else 0


def cmd_overview(args: argparse.Namespace) -> None:
    """List every case with its reference, retention date and legal hold (one passphrase).

    With ``--due`` only the cases past their retention date without a legal hold are listed, for
    the periodic retention review; Ridge never disposes of them by itself.
    """
    cases = store_overview(args.store, common.read_passphrase(), common.KEYSTORE_FACTORY())
    if args.due:
        cases = [c for c in cases if c.due]
        common.say(f"{len(cases)} case(s) past their retention date without a legal hold")
    for c in cases:
        if c.reference is None:
            common.say(f"{c.case_id}  {c.state}{f': {c.problem}' if c.problem else ''}")
            continue
        flags = "legal hold" if c.legal_hold else ("retention reached" if c.due else "")
        common.say(
            f"{c.case_id}  {c.reference}  keep until {c.retention_until}  "
            f"{c.evidence} evidence, {c.jobs} job(s)  {flags}".rstrip()
        )


def add_commands(sub: Any) -> None:
    """Register the store commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("verify-store", help="verify every case of a store (hashes, custody chains, signatures)")
    p.add_argument("--store", type=Path, required=True)
    p.set_defaults(func=cmd_verify_store)
    p = sub.add_parser("overview", help="every case with its reference, retention date and legal hold")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--due", action="store_true", help="only cases past their retention date without a legal hold")
    p.set_defaults(func=cmd_overview)
