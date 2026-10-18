"""``ridge-case`` disclosure packages: export a case's signed records, verify a package offline.

ridge-case package CASE --to NEW_FOLDER
ridge-case check-package FOLDER [--key-id KEY_ID]          (no case store needed)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.identity import unlock_identity
from ridge.case.package import check_package, export_package
from ridge.case.store import open_case


def cmd_package(args: argparse.Namespace) -> None:
    """Write a disclosure package (signed records, no images) to a new folder."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    with open_case(args.case, passphrase, keystore) as case:
        manifest = export_package(case, args.case.parent, signer, args.to)
    reports = sum(1 for f in manifest["files"] if f["path"].endswith(".json") and f["path"].startswith("reports/"))
    common.say(f"package {manifest['package_id']} written to {args.to}: processing record and {reports} report(s)")
    common.say(f"signed with key {signer.key_id}; verify with: ridge-case check-package {args.to}")


def cmd_check_package(args: argparse.Namespace) -> int:
    """Verify a disclosure package without opening any case."""
    check = check_package(args.folder, expected_key_id=args.key_id)
    common.say(
        f"package {check.package_id} verified: case {check.case_id}, {check.reports} report(s), "
        f"processing record with {check.record_entries} entries, key {check.key_id}"
    )
    if not check.key_confirmed:
        common.say(f"confirm key {check.key_id} is the examiner's key, or pass --key-id")
    return 0


def add_commands(sub: Any) -> None:
    """Register the package commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("package", help="write a case's signed records to a new folder (no images)")
    p.add_argument("case", type=Path)
    p.add_argument("--to", type=Path, required=True, help="a folder that does not exist yet")
    p.set_defaults(func=cmd_package)
    p = sub.add_parser("check-package", help="verify a disclosure package without the case store")
    p.add_argument("folder", type=Path)
    p.add_argument("--key-id", help="the examiner key id the package must be signed with")
    p.set_defaults(func=cmd_check_package)
