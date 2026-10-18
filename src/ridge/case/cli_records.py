"""``ridge-case`` records commands: jobs, signed reports, reproduction, processing record (FR-28, FR-34, PRIV-3).

ridge-case jobs CASE
ridge-case report CASE JOB [--json | --to PATH [--overwrite]]
ridge-case reproduce CASE JOB                (re-run from the report; compare every output)
ridge-case check-report REPORT.json [--sig PATH] [--key-id KEY_ID]     (no case store needed)
ridge-case log CASE [--to PATH [--overwrite]]   (custody log; --to writes the signed record)
ridge-case check-log RECORD.json [--key-id KEY_ID]                     (no case store needed)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.custody_head import check_head, export_head
from ridge.case.identity import unlock_identity
from ridge.case.limits import FILE as LIMITS_FILE
from ridge.case.limits import MAX_BYTES as LIMITS_MAX_BYTES
from ridge.case.limits import load_limits, parse_limits
from ridge.case.processing_record import check_exported_log, export_log
from ridge.case.reports import check_exported_report, export_report, list_jobs, load_report, printable, render_report
from ridge.case.reproduce import reproduce_job
from ridge.case.store import open_case
from ridge.image_io import read_bounded


def cmd_jobs(args: argparse.Namespace) -> None:
    """List the jobs recorded in the custody log."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        jobs = list_jobs(case.entries)
    if not jobs:
        common.say("no jobs")
    for job in jobs:
        signed = "signed report" if job.report_sha256 else "no report"
        error = f"  ({printable(job.error)})" if job.error else ""
        common.say(
            f"{job.job_id}  {job.started_utc}  {job.result:6}  evidence {job.evidence_sha256[:12]}  {signed}{error}"
        )


def cmd_report(args: argparse.Namespace) -> None:
    """Show or export a job's signed report after verifying it."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        if args.to:
            signed = export_report(case, args.case.parent, args.job, args.to, overwrite=args.overwrite)
            common.say(
                f"report {signed.job_id} exported to {args.to} (signature: {args.to.name}.sig, key {signed.key_id})"
            )
            return
        signed = load_report(case, args.case.parent, args.job)
    common.say(signed.canonical.decode("utf-8") if args.json else render_report(signed.report, signed.key_id))


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Re-run a signed job from its report and compare every output (exit 1 on any difference)."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    with open_case(args.case, passphrase, keystore) as case:
        result = reproduce_job(case, args.case.parent, signer, args.job, nfiq2_command=common.nfiq2_command(args))
    for key, (before, now) in result.environment_changes.items():
        common.say(f"environment changed: {key}: {printable(before)} -> {printable(now)}")
    if result.identical:
        common.say(
            f"reproduced: job {result.original_job} re-run as {result.new_job}, {len(result.matched)} identical outputs"
        )
        return 0
    for label, items in (("differs", result.differing), ("missing", result.missing), ("extra", result.extra)):
        for item in items:
            print(f"{label}: {printable(item)}", file=sys.stderr)  # noqa: T201
    common.say(
        f"NOT reproduced: job {result.original_job} re-run as {result.new_job}; {len(result.matched)} outputs match"
    )
    return 1


def cmd_check_report(args: argparse.Namespace) -> int:
    """Verify an exported report and its signature without opening any case."""
    check = check_exported_report(args.report, args.sig, expected_key_id=args.key_id)
    common.say(f"signature valid: job {check.job_id}, case {check.case_id}, created {check.created_utc}")
    if check.key_confirmed:
        common.say(f"signed by the expected key {check.key_id}")
    else:
        common.say(
            f"signed by key {check.key_id}: confirm it is the examiner's key (ridge-case identity show), "
            "or pass --key-id"
        )
    return 0


def cmd_log(args: argparse.Namespace) -> None:
    """Print the decrypted custody log as JSON lines, or export it as a signed processing record."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    if args.to:
        signer = unlock_identity(args.case.parent, passphrase, keystore)
        with open_case(args.case, passphrase, keystore) as case:
            count = export_log(case, args.case.parent, signer, args.to, overwrite=args.overwrite)
        common.say(f"processing record with {count} entries exported to {args.to} (signed by key {signer.key_id})")
        return
    with open_case(args.case, passphrase, keystore) as case:
        for entry in case.entries:
            common.say(json.dumps(entry, ensure_ascii=False, sort_keys=True))


def cmd_check_log(args: argparse.Namespace) -> int:
    """Verify an exported processing record without opening any case."""
    check = check_exported_log(args.record, expected_key_id=args.key_id)
    common.say(
        f"chain intact: case {check.case_id}, {check.entries} entries, {check.signed_heads} signed head(s), "
        "ending with the signed export"
    )
    if check.key_confirmed:
        common.say(f"signed by the expected key {check.key_id}")
    else:
        common.say(f"signed by key {check.key_id}: confirm it is the examiner's key, or pass --key-id")
    return 0


def cmd_head(args: argparse.Namespace) -> None:
    """Export the signed custody head for out-of-band countersigning by a laboratory system (OQ-8)."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    with open_case(args.case, passphrase, keystore) as case:
        doc = export_head(case, args.case.parent, signer, args.to, overwrite=args.overwrite)
    common.say(f"custody head at entry {doc['seq']} ({doc['head'][:16]}...) exported to {args.to}")
    common.say("give it to the laboratory system to countersign or timestamp; check later records against it")


def cmd_check_head(args: argparse.Namespace) -> int:
    """Verify a custody head and, with --record, that a later processing record still contains it."""
    check = check_head(args.head, record=args.record, expected_key_id=args.key_id)
    common.say(f"custody head verified: case {check.case_id}, entry {check.seq}, key {check.key_id}")
    if check.record_entries is not None:
        common.say(f"the processing record ({check.record_entries} entries) contains this head unchanged")
    if not check.key_confirmed:
        common.say(f"confirm key {check.key_id} is the examiner's key, or pass --key-id")
    return 0


def cmd_limits(args: argparse.Namespace) -> None:
    """Show a store's limits of use, or check a limits file before the laboratory places it in a store."""
    limits = parse_limits(read_bounded(args.check, LIMITS_MAX_BYTES)) if args.check else load_limits(args.store)
    if limits is None:
        common.say(f"no limits of use configured ({args.store / LIMITS_FILE} does not exist)")
        return
    common.say(f"limits of use from {limits.source}, sha256 {limits.sha256}")
    for key, value in limits.to_json().items():
        common.say(f"  {key}: {value}")


def add_commands(sub: Any) -> None:
    """Register the records commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("jobs", help="list jobs from the custody log")
    p.add_argument("case", type=Path)
    p.set_defaults(func=cmd_jobs)
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
    p = sub.add_parser("head", help="export the signed custody head for out-of-band countersigning (OQ-8)")
    p.add_argument("case", type=Path)
    p.add_argument("--to", type=Path, required=True, help="where to write the signed head (JSON)")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_head)
    p = sub.add_parser("check-head", help="verify a custody head, and that a later record still contains it")
    p.add_argument("head", type=Path)
    p.add_argument("--record", type=Path, help="a later processing record (ridge-case log --to)")
    p.add_argument("--key-id", help="the examiner key id the head must be signed with")
    p.set_defaults(func=cmd_check_head)
    p = sub.add_parser("limits", help="show a store's limits of use, or check a limits file (PRD section 12)")
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--store", type=Path, help="the case store whose limits-of-use.json to show")
    where.add_argument("--check", type=Path, help="a limits file to validate before it is placed in a store")
    p.set_defaults(func=cmd_limits)
