"""``ridge-case`` records commands: jobs, signed reports, reproduction, processing record (FR-28, FR-34, PRIV-3).

ridge-case jobs CASE
ridge-case report CASE JOB [--json | --to PATH | --html PATH] [--overwrite]
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
from ridge.case.cli_register import add_register_argument, confirm, registered_line
from ridge.case.custody_head import check_head, export_head
from ridge.case.identity import unlock_identity
from ridge.case.job_compare import differences, render_differences
from ridge.case.processing_record import LogCheck, check_exported_log, export_log
from ridge.case.record_html import write_record_html
from ridge.case.report_html import export_report_html, write_exported_report_html
from ridge.case.reports import (
    ReportCheck,
    check_exported_report,
    export_report,
    list_jobs,
    load_report,
    printable,
    render_report,
)
from ridge.case.reproduce import reproduce_job
from ridge.case.store import open_case


def cmd_jobs(args: argparse.Namespace) -> None:
    """List the jobs recorded in the custody log."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        jobs = list_jobs(case.entries)
    if args.json:
        common.say(json.dumps([j.to_json() for j in jobs], ensure_ascii=False, indent=2))
        return
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
        if args.html:
            signed = export_report_html(case, args.case.parent, args.job, args.html, overwrite=args.overwrite)
            common.say(f"readable report {signed.job_id} written to {args.html} (the signed JSON stays authoritative)")
            return
        if args.to:
            signed = export_report(case, args.case.parent, args.job, args.to, overwrite=args.overwrite)
            common.say(
                f"report {signed.job_id} exported to {args.to} (signature: {args.to.name}.sig, key {signed.key_id})"
            )
            return
        signed = load_report(case, args.case.parent, args.job)
    common.say(signed.canonical.decode("utf-8") if args.json else render_report(signed.report, signed.key_id))


def cmd_compare_jobs(args: argparse.Namespace) -> None:
    """List the settings that differ between two jobs (both reports verified; the reads are logged)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        first = load_report(case, args.case.parent, args.job)
        second = load_report(case, args.case.parent, args.other)
    rows, same = differences(first.report, second.report)
    for line in render_differences(first.job_id, second.job_id, rows, same):
        common.say(line)


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
    """Verify an exported report and its signature without opening any case (and write a readable copy).

    With ``--register`` the signer is checked before a readable copy is written.
    """
    holder: list[str | None] = []

    def check_signer(c: ReportCheck) -> None:
        holder.append(registered_line(args, c.key_id, "examiner", c.created_utc))

    if args.html:
        check = write_exported_report_html(
            args.report, args.html, sig_path=args.sig, expected_key_id=args.key_id, confirm=check_signer
        )
    else:
        check = check_exported_report(args.report, args.sig, expected_key_id=args.key_id)
        check_signer(check)
    common.say(f"signature valid: job {check.job_id}, case {check.case_id}, created {check.created_utc}")
    if args.html:
        common.say(f"readable copy written to {args.html}")
    if holder[0] is not None:
        common.say(holder[0])
        return 0
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
            if args.kind is None or entry["action"] == args.kind or entry["action"].startswith(f"{args.kind}."):
                common.say(json.dumps(entry, ensure_ascii=False, sort_keys=True))


def cmd_check_log(args: argparse.Namespace) -> int:
    """Verify an exported processing record without opening any case (and write a readable copy).

    With ``--register`` the signer is checked before a readable copy is written.
    """
    holder: list[str | None] = []

    def check_signer(c: LogCheck) -> None:
        holder.append(registered_line(args, c.key_id, "examiner", c.exported_utc))

    if args.html:
        check = write_record_html(args.record, args.html, expected_key_id=args.key_id, confirm=check_signer)
    else:
        check = check_exported_log(args.record, expected_key_id=args.key_id)
        check_signer(check)
    if args.html:
        common.say(f"readable copy written to {args.html}")
    common.say(
        f"chain intact: case {check.case_id}, {check.entries} entries, {check.signed_heads} signed head(s), "
        "ending with the signed export"
    )
    if holder[0] is not None:
        common.say(holder[0])
        return 0
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
    if not confirm(args, check.key_id, "examiner", check.signed_utc) and not check.key_confirmed:
        common.say(f"confirm key {check.key_id} is the examiner's key, or pass --key-id")
    return 0


def add_commands(sub: Any) -> None:
    """Register the records commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("jobs", help="list jobs from the custody log")
    p.add_argument("case", type=Path)
    p.add_argument("--json", action="store_true", help="print the jobs as JSON (for laboratory scripts)")
    p.set_defaults(func=cmd_jobs)
    p = sub.add_parser("report", help="show or export a job's signed report (verified first)")
    p.add_argument("case", type=Path)
    p.add_argument("job", help="job id, or its first 8 or more characters")
    shown = p.add_mutually_exclusive_group()
    shown.add_argument("--json", action="store_true", help="print the signed canonical JSON")
    shown.add_argument("--to", type=Path, help="export the report and its detached signature (PATH.sig)")
    shown.add_argument("--html", type=Path, help="write a readable HTML rendering (not signed; logged)")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_report)
    p = sub.add_parser("compare-jobs", help="list the settings that differ between two jobs (no ranking)")
    p.add_argument("case", type=Path)
    p.add_argument("job", help="job id, or its first 8 or more characters")
    p.add_argument("other", help="the other job id, or its first 8 or more characters")
    p.set_defaults(func=cmd_compare_jobs)
    p = sub.add_parser("reproduce", help="re-run a signed job from its report and compare every output")
    p.add_argument("case", type=Path)
    p.add_argument("job", help="job id, or its first 8 or more characters")
    p.add_argument("--nfiq2", type=Path, help="absolute path of the NIST NFIQ 2 executable (score is not compared)")
    p.add_argument("--nfiq2-arg", action="append", default=[], help="extra argument for the NFIQ 2 command")
    p.set_defaults(func=cmd_reproduce)
    _add_record_commands(sub)


def _add_record_commands(sub: Any) -> None:
    """Register the verification and processing-record commands."""
    p = sub.add_parser("check-report", help="verify an exported report without the case store")
    p.add_argument("report", type=Path)
    p.add_argument("--sig", type=Path, help="detached signature (default: REPORT.sig)")
    p.add_argument("--key-id", help="the examiner key id the report must be signed with")
    p.add_argument("--html", type=Path, help="after verifying, write a readable copy here (a new file)")
    add_register_argument(p)
    p.set_defaults(func=cmd_check_report)
    p = sub.add_parser("log", help="print the custody log, or export it as a signed processing record")
    p.add_argument("case", type=Path)
    p.add_argument("--to", type=Path, help="write a signed, verifiable processing record (JSON)")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--kind", help="print only entries of one kind, for example job or examiner.note")
    p.set_defaults(func=cmd_log)
    p = sub.add_parser("check-log", help="verify an exported processing record without the case store")
    p.add_argument("record", type=Path)
    p.add_argument("--key-id", help="the examiner key id the record must be signed with")
    p.add_argument("--html", type=Path, help="after verifying, write a readable copy here (a new file)")
    add_register_argument(p)
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
    add_register_argument(p)
    p.set_defaults(func=cmd_check_head)
