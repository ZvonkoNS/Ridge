"""``ridge-case recovery``: export, import and check a device-secret recovery file (ADR-012)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.recovery import export_recovery, import_recovery, read_recovery
from ridge.case.reports import printable
from ridge.case.store_audit import FILE as AUDIT_FILE


def cmd_export(args: argparse.Namespace) -> None:
    """Seal this account's device secret under a new recovery passphrase."""
    examiner = common.read_passphrase()
    recovery = common.read_passphrase(confirm=True, prompt="New recovery passphrase (not the examiner's): ")
    info = export_recovery(args.store, examiner, recovery, common.KEYSTORE_FACTORY(), args.to)
    common.say(f"recovery file for key {info.key_id} (fingerprint {info.fingerprint}) written to {args.to}")
    common.say(f"keep it apart from the recovery passphrase; the export is logged in {AUDIT_FILE}")


def cmd_import(args: argparse.Namespace) -> None:
    """Restore a device secret into this account's keystore, after proving it opens the store."""
    recovery = common.read_passphrase(prompt="Recovery passphrase: ")
    examiner = common.read_passphrase()
    info = import_recovery(args.file, recovery, args.store, examiner, common.KEYSTORE_FACTORY())
    common.say(f"device secret (fingerprint {info.fingerprint}) restored into this account's OS keystore")
    common.say(f"the store's cases open again with the examiner passphrase; the import is logged in {AUDIT_FILE}")


def cmd_check(args: argparse.Namespace) -> None:
    """Show what a recovery file says about itself (it is not opened; no passphrase)."""
    info, _ = read_recovery(args.file)
    common.say(printable(f"device-secret recovery file for key {info.key_id}, made {info.created_utc}"))
    common.say(printable(f"secret fingerprint {info.fingerprint}; opening it needs the recovery passphrase"))


def add_commands(sub: Any) -> None:
    """Register ``recovery export|import|check`` on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("recovery", help="device-secret recovery file (ADR-012)")
    rsub = p.add_subparsers(dest="recovery_command", required=True)
    e = rsub.add_parser("export", help="seal this account's device secret under a recovery passphrase")
    e.add_argument("--store", type=Path, required=True, help="the store whose identity proves the examiner is present")
    e.add_argument("--to", type=Path, required=True, help="a new file")
    e.set_defaults(func=cmd_export)
    i = rsub.add_parser("import", help="restore a device secret into an account that has none")
    i.add_argument("file", type=Path)
    i.add_argument("--store", type=Path, required=True, help="the store the secret must open")
    i.set_defaults(func=cmd_import)
    c = rsub.add_parser("check", help="show what a recovery file says about itself (not opened)")
    c.add_argument("file", type=Path)
    c.set_defaults(func=cmd_check)
