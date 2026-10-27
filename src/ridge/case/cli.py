"""``ridge-case``: encrypted case store, custody log, signed jobs and verification.

    ridge-case identity init --store STORE
    ridge-case init --store STORE --reference REF --legal-basis TEXT --retention YYYY-MM-DD
    ridge-case cases --store STORE              (ids and states only; no passphrase needed)
    ridge-case import CASE photo.jpg [more...] [--source TEXT]
    ridge-case list CASE | verify CASE
    ridge-case export CASE SHA --to PATH [--overwrite]
    ridge-case hold CASE --on|--off --reason TEXT
    ridge-case dispose CASE --confirm CASE_ID --reason TEXT [--before-retention]

Extraction (``ridge-case extract``) lives in ``ridge.case.cli_extract``; records commands (jobs,
report, reproduce, check-report, log, check-log) in
``ridge.case.cli_records``; comparison commands (import-reference, compare) in ``ridge.case.cli_compare``;
a photo's metadata (``ridge-case metadata``) in ``ridge.case.cli_metadata``.
Passphrases are only read interactively (never from arguments or the environment).
Exit codes: 0 ok, 1 refused or failed (message on stderr), 2 usage error, 3 internal error.
"""

from __future__ import annotations

import argparse
import json
import traceback
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from ridge.case import (
    cli_annotations,
    cli_check,
    cli_compare,
    cli_extract,
    cli_limits,
    cli_metadata,
    cli_notes,
    cli_package,
    cli_records,
    cli_recovery,
    cli_register,
    cli_store,
    cli_sweep,
    cli_triage,
)
from ridge.case import cli_common as common
from ridge.case.dispose import REASONS, dispose_case
from ridge.case.export_all import INDEX, ROLES, export_role
from ridge.case.export_file import export_item
from ridge.case.identity import create_identity, public_identity, unlock_identity
from ridge.case.keys import b64
from ridge.case.listing import list_cases
from ridge.case.reports import printable
from ridge.case.store import create_case, open_case
from ridge.case.verify import verify_case
from ridge.errors import RidgeError
from ridge.export.formats import FORMATS


def cmd_identity(args: argparse.Namespace) -> None:
    """Create or show the examiner signing identity."""
    if args.action == "init":
        passphrase = common.read_passphrase(confirm=True)
        signer = create_identity(args.store, passphrase, common.KEYSTORE_FACTORY(), common.KDF_PARAMS)
        common.say(f"identity created: key id {signer.key_id}")
    key_id, public = public_identity(args.store)
    common.say(f"key id {key_id}")
    common.say(f"public key (Ed25519, base64) {b64(public)}")


def cmd_init(args: argparse.Namespace) -> None:
    """Create a case protected by the examiner passphrase (the one that unlocks the identity)."""
    public_identity(args.store)  # a signing identity must exist first
    passphrase, keystore = common.read_passphrase(confirm=True), common.KEYSTORE_FACTORY()
    unlock_identity(args.store, passphrase, keystore)  # one passphrase for identity and cases (extract needs both)
    case_dir = create_case(
        args.store,
        case_reference=args.reference,
        legal_basis=args.legal_basis,
        retention_until=date.fromisoformat(args.retention),
        passphrase=passphrase,
        keystore=keystore,
        params=common.KDF_PARAMS,
    )
    common.say(f"case created: {case_dir}")


def cmd_cases(args: argparse.Namespace) -> None:
    """List the cases of a store without unlocking anything."""
    cases = list_cases(args.store)
    if not cases:
        common.say("no cases")
    for case in cases:
        when = case.created_utc or case.disposed_utc or "-"
        common.say(f"{case.case_id}  {case.state:8}  {when}")


def cmd_import(args: argparse.Namespace) -> None:
    """Import evidence photos."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        for path in args.files:
            item = case.import_evidence(path, source=args.source)
            common.say(f"{path} -> evidence {item.sha256}  ({item.size} bytes)")


def cmd_list(args: argparse.Namespace) -> None:
    """List stored items."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        meta = case.meta()
        common.say(f"case {case.case_id}  reference {meta.case_reference}  retention until {meta.retention_until}")
        common.say(f"legal hold: {'yes' if meta.legal_hold else 'no'}  custody entries: {len(case.entries)}")
        for item in case.items():
            note = f"  [{printable(item.source)}]" if item.source else ""
            label = printable(item.label)
            common.say(f"{item.role:9} {item.sha256}  {item.size:>10}  {label}  {item.job_id or ''}{note}")


def cmd_export(args: argparse.Namespace) -> None:
    """Export one item in plaintext to an examiner-chosen path (a .tif/.tiff or .bmp name converts an image)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        done = export_item(case, args.sha, args.to, overwrite=args.overwrite)
    if done.format:
        common.say(f"exported to {done.path} as {done.format} (sha256 of the file {done.sha256})")
    else:
        common.say(f"exported to {done.path}")


def cmd_export_all(args: argparse.Namespace) -> None:
    """Export every stored item of one role into a new folder (each export logged)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        written = export_role(case, args.role, args.to, fmt=args.format)
    common.say(
        f"{len(written)} {args.role} file(s) exported to {args.to}, listed in {INDEX}; each is in the custody log"
    )


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify hashes, chain and signatures."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        result = verify_case(case, args.case.parent)
    if args.json:
        common.say(json.dumps({**asdict(result), "ok": result.ok}, ensure_ascii=False, indent=2), lines=True)
        return 0 if result.ok else 1
    counts = f"items {result.items}, reports {result.reports}, signed heads {result.signed_heads}"
    common.say(f"custody entries {result.entries}, {counts}")
    for problem in result.problems:
        common.warn(f"PROBLEM: {problem}")
    common.say("verification passed" if result.ok else f"verification FAILED ({len(result.problems)} problem(s))")
    return 0 if result.ok else 1


def cmd_hold(args: argparse.Namespace) -> None:
    """Place or lift a legal hold."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        case.set_legal_hold(args.on, args.reason)
    common.say(f"legal hold {'placed' if args.on else 'lifted'}")


def cmd_dispose(args: argparse.Namespace) -> None:
    """Crypto-erase a case."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    record = dispose_case(
        args.case,
        passphrase,
        keystore,
        confirm_case_id=args.confirm,
        reason=args.reason,
        actor_key_id=signer.key_id,
        before_retention=args.before_retention,
    )
    common.say(f"case disposed; record kept at {record}")


def build_parser() -> argparse.ArgumentParser:
    """Argument parser with one sub-command per case operation."""
    ap = argparse.ArgumentParser(prog="ridge-case", description="Ridge encrypted case store.")
    ap.add_argument("--verbose", action="store_true", help="print tracebacks for internal errors")
    sub = ap.add_subparsers(dest="command", required=True)
    _add_store_commands(sub)
    _add_case_commands(sub)
    cli_extract.add_commands(sub)
    cli_records.add_commands(sub)
    cli_compare.add_commands(sub)
    cli_store.add_commands(sub)
    cli_notes.add_commands(sub)
    cli_metadata.add_commands(sub)
    cli_limits.add_commands(sub)
    cli_package.add_commands(sub)
    cli_register.add_commands(sub)
    cli_recovery.add_commands(sub)
    cli_sweep.add_commands(sub)
    cli_check.add_commands(sub)
    cli_annotations.add_commands(sub)
    cli_triage.add_commands(sub)
    return ap


def _add_store_commands(sub: Any) -> None:
    p = sub.add_parser("identity", help="examiner signing identity")
    p.add_argument("action", choices=["init", "show"])
    p.add_argument("--store", type=Path, required=True)
    p.set_defaults(func=cmd_identity)
    p = sub.add_parser("cases", help="list the cases of a store (no passphrase needed)")
    p.add_argument("--store", type=Path, required=True)
    p.set_defaults(func=cmd_cases)
    p = sub.add_parser("init", help="create a case")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--reference", required=True, help="case reference (stored encrypted)")
    p.add_argument("--legal-basis", required=True, help="legal basis for processing (stored encrypted)")
    p.add_argument("--retention", required=True, help="retention date, YYYY-MM-DD")
    p.set_defaults(func=cmd_init)


def _add_case_commands(sub: Any) -> None:
    p = sub.add_parser("list", help="list stored items")
    p.add_argument("case", type=Path)
    p.set_defaults(func=cmd_list)
    p = sub.add_parser("export-all", help="export every stored item of one role into a new folder (logged)")
    p.add_argument("case", type=Path)
    p.add_argument("--to", type=Path, required=True, help="a folder that does not exist yet")
    p.add_argument(
        "--role", choices=ROLES, default="export-gray", help="which items (default: grayscale comparison exports)"
    )
    p.add_argument(
        "--format",
        choices=FORMATS,
        help="convert image outputs to uncompressed tiff or bmp with their resolution (default: as stored, png)",
    )
    p.set_defaults(func=cmd_export_all)
    p = sub.add_parser("verify", help="verify the case")
    p.add_argument("case", type=Path)
    p.add_argument("--json", action="store_true", help="print the result as JSON (for laboratory monitoring)")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("import", help="import evidence photos")
    p.add_argument("case", type=Path)
    p.add_argument("files", type=Path, nargs="+")
    p.add_argument("--source", help="where the photos came from, e.g. 'Exhibit 12, phone of suspect A'")
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("export", help="export one item in plaintext")
    p.add_argument("case", type=Path)
    p.add_argument("sha")
    p.add_argument(
        "--to", type=Path, required=True, help="destination; .tif/.tiff or .bmp converts an image output (FR-32)"
    )
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_export)
    p = sub.add_parser("hold", help="place or lift a legal hold")
    p.add_argument("case", type=Path)
    p.add_argument("--reason", required=True)
    state = p.add_mutually_exclusive_group(required=True)
    state.add_argument("--on", dest="on", action="store_true")
    state.add_argument("--off", dest="on", action="store_false")
    p.set_defaults(func=cmd_hold)
    p = sub.add_parser("dispose", help="crypto-erase a case")
    p.add_argument("case", type=Path)
    p.add_argument("--confirm", required=True, metavar="CASE_ID")
    p.add_argument("--reason", required=True, choices=REASONS, help="reason code kept in the disposal record")
    p.add_argument("--before-retention", action="store_true")
    p.set_defaults(func=cmd_dispose)


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``ridge-case`` and return the exit code."""
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        code = args.func(args)
    except (RidgeError, ValueError) as exc:
        common.warn(f"ridge-case: {exc}")
        return 1
    except OSError as exc:
        common.warn(f"ridge-case: {exc.strerror or type(exc).__name__}: {exc.filename or ''}")
        return 1
    except Exception as exc:  # noqa: BLE001  # a bug: report without leaking data
        common.warn(f"ridge-case: internal error ({type(exc).__name__}); rerun with --verbose and report it")
        if args.verbose:
            common.warn(traceback.format_exc().rstrip(), lines=True)  # Ridge's code locations and messages
        return 3
    return int(code or 0)
