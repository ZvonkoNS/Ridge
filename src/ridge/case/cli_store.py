"""Store-level ``ridge-case`` commands: verify, overview, status, backup and the workstation check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.backup import backup_store, check_backup
from ridge.case.case_status import case_status, render_status
from ridge.case.reports import printable
from ridge.case.store import open_case
from ridge.case.store_overview import store_overview
from ridge.case.store_verify import verify_store
from ridge.case.workstation import check_workstation


def cmd_verify_store(args: argparse.Namespace) -> int:
    """Verify every active case of a store; exit 1 when any case failed or cannot be read."""
    results = verify_store(args.store, common.read_passphrase(), common.KEYSTORE_FACTORY())
    if args.json:
        common.say(json.dumps([r.to_json() for r in results], ensure_ascii=False, indent=2))
        return 1 if any(not r.ok for r in results) else 0
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
    if args.json:
        common.say(json.dumps([c.to_json() for c in cases], ensure_ascii=False, indent=2))
        return
    if args.due:
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


def cmd_status(args: argparse.Namespace) -> None:
    """Summarise one case: what is stored, jobs, notes, retention and the last verification."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        status = case_status(case)
    if args.json:
        common.say(json.dumps(status.to_json(), ensure_ascii=False, indent=2))
        return
    for line in render_status(status):
        common.say(printable(line))


def cmd_backup(args: argparse.Namespace) -> None:
    """Copy the encrypted store to a new folder with a hash manifest (no passphrase needed)."""
    manifest = backup_store(args.store, args.to)
    size = sum(f["size"] for f in manifest["files"])
    common.say(f"backup of {len(manifest['files'])} file(s), {size} bytes, written to {args.to}")
    common.say("it holds the encrypted store only: restoring it also needs the examiner's OS-keystore secret")


def cmd_check_backup(args: argparse.Namespace) -> int:
    """Verify every file of a store backup against its manifest."""
    check = check_backup(args.folder)
    common.say(f"backup verified: {check.files} file(s), {check.bytes} bytes, made {check.created_utc}")
    return 0


def cmd_workstation(args: argparse.Namespace) -> int:
    """Check the installation, the OS keystore, the store and its limits; exit 1 on any problem."""
    found = check_workstation(args.store, common.KEYSTORE_FACTORY(), args.register)
    if args.json:
        common.say(json.dumps([f.to_json() for f in found], ensure_ascii=False, indent=2))
    else:
        for f in found:
            common.say(printable(f"{f.level.upper():8} {f.topic}: {f.text}"))
        common.say("this checks the setup; it does not validate the method or the installation")
    return 1 if any(f.level == "problem" for f in found) else 0


def add_commands(sub: Any) -> None:
    """Register the store commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("verify-store", help="verify every case of a store (hashes, custody chains, signatures)")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--json", action="store_true", help="print every case's result as JSON (for laboratory monitoring)")
    p.set_defaults(func=cmd_verify_store)
    p = sub.add_parser("backup", help="copy the encrypted store to a new folder with a hash manifest")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--to", type=Path, required=True, help="a folder that does not exist yet")
    p.set_defaults(func=cmd_backup)
    p = sub.add_parser("check-backup", help="verify a store backup against its manifest")
    p.add_argument("folder", type=Path)
    p.set_defaults(func=cmd_check_backup)
    p = sub.add_parser("status", help="a one-screen summary of a case (reads only)")
    p.add_argument("case", type=Path)
    p.add_argument("--json", action="store_true", help="print the summary as JSON (for laboratory scripts)")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("overview", help="every case with its reference, retention date and legal hold")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--due", action="store_true", help="only cases past their retention date without a legal hold")
    p.add_argument("--json", action="store_true", help="print the cases as JSON (for laboratory scripts)")
    p.set_defaults(func=cmd_overview)
    p = sub.add_parser("workstation", help="check this installation, the OS keystore, the store and its limits")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--register", type=Path, help="also check that this store's signing key is in a key register")
    p.add_argument("--json", action="store_true", help="print the findings as JSON (for laboratory scripts)")
    p.set_defaults(func=cmd_workstation)
