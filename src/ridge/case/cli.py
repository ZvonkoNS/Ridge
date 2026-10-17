"""``ridge-case``: encrypted case store, custody log, signed jobs and verification.

    ridge-case identity init --store STORE
    ridge-case init --store STORE --reference REF --legal-basis TEXT --retention YYYY-MM-DD
    ridge-case import CASE photo.jpg [more...]
    ridge-case extract CASE --all            (or --evidence SHA ...) [extraction options]
    ridge-case list CASE | log CASE | verify CASE
    ridge-case export CASE SHA --to PATH [--overwrite]
    ridge-case hold CASE --on|--off --reason TEXT
    ridge-case dispose CASE --confirm CASE_ID --reason TEXT [--before-retention]

Passphrases are only read interactively (never from arguments or the environment).
Exit codes: 0 ok, 1 refused or failed (message on stderr), 2 usage error, 3 internal error.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import traceback
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from ridge.case.dispose import REASONS, dispose_case
from ridge.case.identity import create_identity, public_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.keys import KdfParams, KeyringKeyStore, KeyStore, b64
from ridge.case.store import create_case, open_case
from ridge.case.verify import verify_case
from ridge.errors import ParameterError, RidgeError

KEYSTORE_FACTORY: Callable[[], KeyStore] = KeyringKeyStore  # replaced in tests
KDF_PARAMS = KdfParams()  # replaced in tests with the minimum allowed cost


def read_passphrase(*, confirm: bool = False) -> str:
    """Prompt for the examiner passphrase (twice when setting it)."""
    first = getpass.getpass("Examiner passphrase: ")
    if confirm and getpass.getpass("Repeat passphrase: ") != first:
        raise ParameterError("the passphrases do not match")
    return first


def _say(text: str) -> None:
    print(text)  # noqa: T201  # CLI output


def cmd_identity(args: argparse.Namespace) -> None:
    """Create or show the examiner signing identity."""
    if args.action == "init":
        signer = create_identity(args.store, read_passphrase(confirm=True), KEYSTORE_FACTORY(), KDF_PARAMS)
        _say(f"identity created: key id {signer.key_id}")
    key_id, public = public_identity(args.store)
    _say(f"key id {key_id}\npublic key (Ed25519, base64) {b64(public)}")


def cmd_init(args: argparse.Namespace) -> None:
    """Create a case protected by the examiner passphrase (the one that unlocks the identity)."""
    public_identity(args.store)  # a signing identity must exist first
    passphrase, keystore = read_passphrase(confirm=True), KEYSTORE_FACTORY()
    unlock_identity(args.store, passphrase, keystore)  # one passphrase for identity and cases (extract needs both)
    case_dir = create_case(
        args.store,
        case_reference=args.reference,
        legal_basis=args.legal_basis,
        retention_until=date.fromisoformat(args.retention),
        passphrase=passphrase,
        keystore=keystore,
        params=KDF_PARAMS,
    )
    _say(f"case created: {case_dir}")


def cmd_import(args: argparse.Namespace) -> None:
    """Import evidence photos."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        for path in args.files:
            item = case.import_evidence(path)
            _say(f"{path} -> evidence {item.sha256}  ({item.size} bytes)")


def cmd_extract(args: argparse.Namespace) -> None:
    """Run extraction jobs on evidence."""
    passphrase, keystore = read_passphrase(), KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    params = JobParams(args.period, args.min_quality, args.flip, not args.no_crop, args.debug)
    with open_case(args.case, passphrase, keystore) as case:
        targets = [i.sha256 for i in case.items() if i.role == "evidence"] if args.all else args.evidence
        if not targets:
            raise ParameterError("no evidence selected (use --all or --evidence SHA)")
        for sha in targets:
            outcome = run_extraction_job(case, sha, signer, params)
            period = outcome.report["measurements"]["ridge_period_px"]
            _say(f"job {outcome.job_id}: {sha[:12]} -> {len(outcome.outputs)} output(s), ridge spacing {period:.1f}px")


def cmd_list(args: argparse.Namespace) -> None:
    """List stored items."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        meta = case.meta()
        _say(f"case {case.case_id}  reference {meta.case_reference}  retention until {meta.retention_until}")
        _say(f"legal hold: {'yes' if meta.legal_hold else 'no'}  custody entries: {len(case.entries)}")
        for item in case.items():
            _say(f"{item.role:9} {item.sha256}  {item.size:>10}  {item.label}  {item.job_id or ''}")


def cmd_log(args: argparse.Namespace) -> None:
    """Print the decrypted custody log as JSON lines (processing record for the DPO)."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        for entry in case.entries:
            _say(json.dumps(entry, ensure_ascii=False, sort_keys=True))


def cmd_export(args: argparse.Namespace) -> None:
    """Export one item in plaintext to an examiner-chosen path."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        dest = case.export(args.sha, args.to, overwrite=args.overwrite)
        _say(f"exported to {dest}")


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify hashes, chain and signatures."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        result = verify_case(case, args.case.parent)
    counts = f"items {result.items}, reports {result.reports}, signed heads {result.signed_heads}"
    _say(f"custody entries {result.entries}, {counts}")
    for problem in result.problems:
        print(f"PROBLEM: {problem}", file=sys.stderr)  # noqa: T201
    _say("verification passed" if result.ok else f"verification FAILED ({len(result.problems)} problem(s))")
    return 0 if result.ok else 1


def cmd_hold(args: argparse.Namespace) -> None:
    """Place or lift a legal hold."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        case.set_legal_hold(args.on, args.reason)
    _say(f"legal hold {'placed' if args.on else 'lifted'}")


def cmd_dispose(args: argparse.Namespace) -> None:
    """Crypto-erase a case."""
    passphrase, keystore = read_passphrase(), KEYSTORE_FACTORY()
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
    _say(f"case disposed; record kept at {record}")


def build_parser() -> argparse.ArgumentParser:
    """Argument parser with one sub-command per case operation."""
    ap = argparse.ArgumentParser(prog="ridge-case", description="Ridge encrypted case store.")
    ap.add_argument("--verbose", action="store_true", help="print tracebacks for internal errors")
    sub = ap.add_subparsers(dest="command", required=True)
    _add_store_commands(sub)
    _add_case_commands(sub)
    return ap


def _add_store_commands(sub: Any) -> None:
    p = sub.add_parser("identity", help="examiner signing identity")
    p.add_argument("action", choices=["init", "show"])
    p.add_argument("--store", type=Path, required=True)
    p.set_defaults(func=cmd_identity)
    p = sub.add_parser("init", help="create a case")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--reference", required=True, help="case reference (stored encrypted)")
    p.add_argument("--legal-basis", required=True, help="legal basis for processing (stored encrypted)")
    p.add_argument("--retention", required=True, help="retention date, YYYY-MM-DD")
    p.set_defaults(func=cmd_init)


def _add_case_commands(sub: Any) -> None:
    for name, func, help_text in (
        ("list", cmd_list, "list stored items"),
        ("log", cmd_log, "print the custody log"),
        ("verify", cmd_verify, "verify the case"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("case", type=Path)
        p.set_defaults(func=func)
    p = sub.add_parser("import", help="import evidence photos")
    p.add_argument("case", type=Path)
    p.add_argument("files", type=Path, nargs="+")
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("extract", help="run extraction jobs")
    p.add_argument("case", type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="every evidence item")
    group.add_argument("--evidence", nargs="+", default=[], metavar="SHA")
    p.add_argument("--period", type=float)
    p.add_argument("--min-quality", type=float, default=0.25)
    p.add_argument("--flip", action="store_true")
    p.add_argument("--no-crop", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.set_defaults(func=cmd_extract)
    p = sub.add_parser("export", help="export one item in plaintext")
    p.add_argument("case", type=Path)
    p.add_argument("sha")
    p.add_argument("--to", type=Path, required=True)
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
        print(f"ridge-case: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    except OSError as exc:
        print(f"ridge-case: {exc.strerror or type(exc).__name__}: {exc.filename or ''}", file=sys.stderr)  # noqa: T201
        return 1
    except Exception as exc:  # noqa: BLE001  # a bug: report without leaking data
        print(f"ridge-case: internal error ({type(exc).__name__}); rerun with --verbose and report it", file=sys.stderr)  # noqa: T201
        if args.verbose:
            traceback.print_exc()
        return 3
    return int(code or 0)
