"""``ridge-case``: encrypted case store, custody log, signed jobs and verification.

    ridge-case identity init --store STORE
    ridge-case init --store STORE --reference REF --legal-basis TEXT --retention YYYY-MM-DD
    ridge-case cases --store STORE              (ids and states only; no passphrase needed)
    ridge-case import CASE photo.jpg [more...]
    ridge-case import-reference CASE candidate.png --source "NAFIS candidate 3"
    ridge-case compare CASE EXPORT_SHA REFERENCE_SHA --to sheet.png [--reference-ppi 500]
    ridge-case extract CASE --all            (or --evidence SHA ...) [--keep-going] [extraction options]
    ridge-case list CASE | log CASE | verify CASE | jobs CASE
    ridge-case log CASE --to PATH [--overwrite]     (signed processing record for the DPO)
    ridge-case check-log RECORD.json [--key-id KEY_ID]                     (no case store needed)
    ridge-case report CASE JOB [--json | --to PATH [--overwrite]]
    ridge-case reproduce CASE JOB                (re-run from the report; compare every output)
    ridge-case check-report REPORT.json [--sig PATH] [--key-id KEY_ID]     (no case store needed)
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

from ridge.case.compare import SHEET_PPI, export_sheet
from ridge.case.dispose import REASONS, dispose_case
from ridge.case.export_step import ExportOptions
from ridge.case.identity import create_identity, public_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.keys import KdfParams, KeyringKeyStore, KeyStore, b64
from ridge.case.listing import list_cases
from ridge.case.processing_record import check_exported_log, export_log
from ridge.case.reports import check_exported_report, export_report, list_jobs, load_report, printable, render_report
from ridge.case.reproduce import reproduce_job
from ridge.case.store import create_case, open_case
from ridge.case.verify import verify_case
from ridge.errors import ExtractionError, InputError, ParameterError, RidgeError

KEYSTORE_FACTORY: Callable[[], KeyStore] = KeyringKeyStore  # replaced in tests
KDF_PARAMS = KdfParams()  # replaced in tests with the minimum allowed cost
# What --keep-going may skip: problems with one photo or its settings. Case-store, integrity, key,
# custody and output errors are not about one photo and always stop the batch.
PHOTO_REFUSALS = (InputError, ExtractionError, ParameterError)


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


def cmd_import_reference(args: argparse.Namespace) -> None:
    """Import NAFIS/AFIS candidate images for side-by-side viewing (never processed)."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        for path in args.files:
            item = case.import_reference(path, args.source)
            _say(f"{path} -> reference {item.sha256}  ({item.size} bytes)")


def cmd_compare(args: argparse.Namespace) -> None:
    """Write a side-by-side sheet of an export and a reference at equal scale (logged)."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        sheet = export_sheet(
            case,
            args.export,
            args.reference,
            args.to,
            reference_ppi=args.reference_ppi,
            ppi=args.ppi,
            overwrite=args.overwrite,
        )
    _say(
        f"comparison sheet {sheet.sha256[:12]} written to {args.to} at {sheet.ppi:g} ppi "
        f"(reference {sheet.reference_ppi:g} ppi from {sheet.reference_ppi_source}); view aid only, no matching"
    )


def cmd_cases(args: argparse.Namespace) -> None:
    """List the cases of a store without unlocking anything."""
    cases = list_cases(args.store)
    if not cases:
        _say("no cases")
    for case in cases:
        when = case.created_utc or case.disposed_utc or "-"
        _say(f"{case.case_id}  {case.state:8}  {when}")


def cmd_extract(args: argparse.Namespace) -> int:
    """Run extraction jobs on evidence (with --keep-going, a refused photo does not stop the batch)."""
    passphrase, keystore = read_passphrase(), KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    if args.ruler and (args.all or len(args.evidence) != 1):
        raise ParameterError("--ruler describes one photo: use it with exactly one --evidence SHA")
    export = ExportOptions(
        enabled=not args.no_export,
        mirror=not args.no_mirror,
        target_ppi=args.ppi,
        ruler=tuple(args.ruler) if args.ruler else None,
    )
    params = JobParams(args.period, args.min_quality, args.flip, not args.no_crop, args.debug, export, args.minutiae)
    nfiq2 = [str(args.nfiq2), *args.nfiq2_arg] if args.nfiq2 else None
    with open_case(args.case, passphrase, keystore) as case:
        targets = [i.sha256 for i in case.items() if i.role == "evidence"] if args.all else args.evidence
        if not targets:
            raise ParameterError("no evidence selected (use --all or --evidence SHA)")
        failed = 0
        for sha in targets:
            try:
                outcome = run_extraction_job(case, sha, signer, params, nfiq2_command=nfiq2)
            except PHOTO_REFUSALS as exc:  # logged as a failed job; store, custody and output errors stop
                if not args.keep_going:
                    raise
                failed += 1
                print(f"ridge-case: {sha[:12]}: {exc}", file=sys.stderr)  # noqa: T201
                continue
            _say(_job_summary(sha, outcome.job_id, outcome.report, len(outcome.outputs)))
    if failed:
        _say(f"{failed} of {len(targets)} job(s) failed (see the messages above and `ridge-case jobs`)")
    return 1 if failed else 0


def _job_summary(sha: str, job_id: str, report: dict[str, Any], outputs: int) -> str:
    period = report["measurements"]["ridge_period_px"]
    line = f"job {job_id}: {sha[:12]} -> {outputs} output(s), ridge spacing {period:.1f}px"
    export = report.get("export")
    if export and export["produced"]:
        scale = export["scale"]
        line += f"; export {export['ppi']:g} ppi (scale: {scale['method']}, +-{scale['uncertainty_pct']:.1f}%)"
    elif export:
        line += f"; no export: {export['reason']}"
    minutiae = report.get("minutiae")
    if minutiae and minutiae["produced"]:
        line += f"; {minutiae['count']} minutiae (unvalidated)"
    elif minutiae:
        line += f"; no minutiae: {minutiae['reason']}"
    nfiq2 = (report.get("quality") or {}).get("nfiq2")
    if nfiq2 and nfiq2["computed"]:
        line += f"; NFIQ 2 {nfiq2['score']} (indicative)"
    return line


def cmd_list(args: argparse.Namespace) -> None:
    """List stored items."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        meta = case.meta()
        _say(f"case {case.case_id}  reference {meta.case_reference}  retention until {meta.retention_until}")
        _say(f"legal hold: {'yes' if meta.legal_hold else 'no'}  custody entries: {len(case.entries)}")
        for item in case.items():
            _say(f"{item.role:9} {item.sha256}  {item.size:>10}  {item.label}  {item.job_id or ''}")


def cmd_log(args: argparse.Namespace) -> None:
    """Print the decrypted custody log as JSON lines, or export it as a signed processing record."""
    passphrase, keystore = read_passphrase(), KEYSTORE_FACTORY()
    if args.to:
        signer = unlock_identity(args.case.parent, passphrase, keystore)
        with open_case(args.case, passphrase, keystore) as case:
            count = export_log(case, args.case.parent, signer, args.to, overwrite=args.overwrite)
        _say(f"processing record with {count} entries exported to {args.to} (signed by key {signer.key_id})")
        return
    with open_case(args.case, passphrase, keystore) as case:
        for entry in case.entries:
            _say(json.dumps(entry, ensure_ascii=False, sort_keys=True))


def cmd_check_log(args: argparse.Namespace) -> int:
    """Verify an exported processing record without opening any case."""
    check = check_exported_log(args.record, expected_key_id=args.key_id)
    _say(
        f"chain intact: case {check.case_id}, {check.entries} entries, {check.signed_heads} signed head(s), "
        "ending with the signed export"
    )
    if check.key_confirmed:
        _say(f"signed by the expected key {check.key_id}")
    else:
        _say(f"signed by key {check.key_id}: confirm it is the examiner's key, or pass --key-id")
    return 0


def cmd_jobs(args: argparse.Namespace) -> None:
    """List the jobs recorded in the custody log."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        jobs = list_jobs(case.entries)
    if not jobs:
        _say("no jobs")
    for job in jobs:
        signed = "signed report" if job.report_sha256 else "no report"
        error = f"  ({printable(job.error)})" if job.error else ""
        _say(f"{job.job_id}  {job.started_utc}  {job.result:6}  evidence {job.evidence_sha256[:12]}  {signed}{error}")


def cmd_report(args: argparse.Namespace) -> None:
    """Show or export a job's signed report after verifying it."""
    with open_case(args.case, read_passphrase(), KEYSTORE_FACTORY()) as case:
        if args.to:
            signed = export_report(case, args.case.parent, args.job, args.to, overwrite=args.overwrite)
            _say(f"report {signed.job_id} exported to {args.to} (signature: {args.to.name}.sig, key {signed.key_id})")
            return
        signed = load_report(case, args.case.parent, args.job)
    _say(signed.canonical.decode("utf-8") if args.json else render_report(signed.report, signed.key_id))


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Re-run a signed job from its report and compare every output (exit 1 on any difference)."""
    passphrase, keystore = read_passphrase(), KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    nfiq2 = [str(args.nfiq2), *args.nfiq2_arg] if args.nfiq2 else None
    with open_case(args.case, passphrase, keystore) as case:
        result = reproduce_job(case, args.case.parent, signer, args.job, nfiq2_command=nfiq2)
    for key, (before, now) in result.environment_changes.items():
        _say(f"environment changed: {key}: {printable(before)} -> {printable(now)}")
    if result.identical:
        _say(
            f"reproduced: job {result.original_job} re-run as {result.new_job}, {len(result.matched)} identical outputs"
        )
        return 0
    for label, items in (("differs", result.differing), ("missing", result.missing), ("extra", result.extra)):
        for item in items:
            print(f"{label}: {printable(item)}", file=sys.stderr)  # noqa: T201
    _say(f"NOT reproduced: job {result.original_job} re-run as {result.new_job}; {len(result.matched)} outputs match")
    return 1


def cmd_check_report(args: argparse.Namespace) -> int:
    """Verify an exported report and its signature without opening any case."""
    check = check_exported_report(args.report, args.sig, expected_key_id=args.key_id)
    _say(f"signature valid: job {check.job_id}, case {check.case_id}, created {check.created_utc}")
    if check.key_confirmed:
        _say(f"signed by the expected key {check.key_id}")
    else:
        _say(
            f"signed by key {check.key_id}: confirm it is the examiner's key (ridge-case identity show), "
            "or pass --key-id"
        )
    return 0


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
    _add_report_commands(sub)
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
    for name, func, help_text in (
        ("list", cmd_list, "list stored items"),
        ("verify", cmd_verify, "verify the case"),
        ("jobs", cmd_jobs, "list jobs from the custody log"),
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
    p.add_argument("--keep-going", action="store_true", help="continue with the next photo when one is refused")
    p.add_argument("--no-export", action="store_true", help="skip the 500 ppi comparison export")
    p.add_argument("--no-mirror", action="store_true", help="do not mirror the export (photo already mirrored)")
    p.add_argument("--ppi", type=float, default=500.0, help="export resolution (default 500)")
    p.add_argument(
        "--ruler",
        type=float,
        nargs=5,
        metavar=("X1", "Y1", "X2", "Y2", "MM"),
        help="scale from two ruler points in the photo (pixels) MM millimetres apart",
    )
    p.add_argument("--minutiae", action="store_true", help="also store automatic minutiae (unvalidated, M3)")
    p.add_argument("--nfiq2", type=Path, help="absolute path of the NIST NFIQ 2 executable (indicative score)")
    p.add_argument("--nfiq2-arg", action="append", default=[], help="extra argument for the NFIQ 2 command")
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


def _add_report_commands(sub: Any) -> None:
    p = sub.add_parser("import-reference", help="import NAFIS/AFIS candidate images (view only, never processed)")
    p.add_argument("case", type=Path)
    p.add_argument("files", type=Path, nargs="+")
    p.add_argument("--source", required=True, help="where the image came from, e.g. 'NAFIS candidate 3'")
    p.set_defaults(func=cmd_import_reference)
    p = sub.add_parser("compare", help="side-by-side sheet of an export and a reference at equal scale")
    p.add_argument("case", type=Path)
    p.add_argument("export", metavar="EXPORT_SHA")
    p.add_argument("reference", metavar="REFERENCE_SHA")
    p.add_argument("--to", type=Path, required=True)
    p.add_argument("--reference-ppi", type=float, help="the reference's resolution if its file does not declare it")
    p.add_argument("--ppi", type=float, default=SHEET_PPI, help=f"sheet resolution (default {SHEET_PPI:g})")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("report", help="show or export a job's signed report (verified first)")
    p.add_argument("case", type=Path)
    p.add_argument("job", help="job id, or its first 8 or more characters")
    shown = p.add_mutually_exclusive_group()
    shown.add_argument("--json", action="store_true", help="print the signed canonical JSON")
    shown.add_argument("--to", type=Path, help="export the report and its detached signature (PATH.sig)")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_report)
    p = sub.add_parser("reproduce", help="re-run a signed job from its report and compare every output")
    p.add_argument("case", type=Path)
    p.add_argument("job", help="job id, or its first 8 or more characters")
    p.add_argument("--nfiq2", type=Path, help="absolute path of the NIST NFIQ 2 executable (score is not compared)")
    p.add_argument("--nfiq2-arg", action="append", default=[], help="extra argument for the NFIQ 2 command")
    p.set_defaults(func=cmd_reproduce)
    p = sub.add_parser("check-report", help="verify an exported report without the case store")
    p.add_argument("report", type=Path)
    p.add_argument("--sig", type=Path, help="detached signature (default: REPORT.sig)")
    p.add_argument("--key-id", help="the examiner key id the report must be signed with")
    p.set_defaults(func=cmd_check_report)
    p = sub.add_parser("log", help="print the custody log, or export it as a signed processing record")
    p.add_argument("case", type=Path)
    p.add_argument("--to", type=Path, help="write a signed, verifiable processing record (JSON)")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_log)
    p = sub.add_parser("check-log", help="verify an exported processing record without the case store")
    p.add_argument("record", type=Path)
    p.add_argument("--key-id", help="the examiner key id the record must be signed with")
    p.set_defaults(func=cmd_check_log)


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
