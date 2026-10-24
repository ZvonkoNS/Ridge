"""``ridge-case extract``: run signed extraction jobs on evidence photos of a case.

    ridge-case extract CASE --all            (or --evidence SHA ...) [--keep-going] [extraction options]

Each job is logged and signed (``ridge.case.jobs``); with ``--keep-going`` a photo that is refused
does not stop the batch, while case-store, integrity, key, custody and output errors always do.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.export_step import ExportOptions
from ridge.case.identity import Signer, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.report_lines import variants_line
from ridge.case.store import OpenCase, open_case
from ridge.errors import ExtractionError, InputError, ParameterError
from ridge.export import REFERENCE_OBJECTS, ReferenceKind
from ridge.pipeline import CHANNELS, MethodOptions

# What --keep-going may skip: problems with one photo or its settings. Case-store, integrity, key,
# custody and output errors are not about one photo and always stop the batch.
PHOTO_REFUSALS = (InputError, ExtractionError, ParameterError)


def cmd_extract(args: argparse.Namespace) -> int:
    """Run extraction jobs on evidence (with --keep-going, a refused photo does not stop the batch)."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    params = _job_params(args)
    with open_case(args.case, passphrase, keystore) as case:
        targets = [i.sha256 for i in case.items() if i.role == "evidence"] if args.all else args.evidence
        if not targets:
            raise ParameterError("no evidence selected (use --all or --evidence SHA)")
        failed = 0
        for sha in targets:
            failed += not _run_job(case, sha, signer, params, args)
    if failed:
        common.say(f"{failed} of {len(targets)} job(s) failed (see the messages above and `ridge-case jobs`)")
    return 1 if failed else 0


def _scale_reference(args: argparse.Namespace) -> tuple[tuple[float, float, float, float, float] | None, ReferenceKind]:
    """Return the two reference points and what they lie on: --ruler with its distance, or --card with its edge."""
    if args.ruler and args.card:
        raise ParameterError("give --ruler or --card, not both")
    if args.ruler:
        return tuple(args.ruler), "ruler"
    if not args.card:
        return None, "ruler"
    edge, *points = args.card
    if edge not in ("long", "short"):
        raise ParameterError("--card EDGE must be long or short")
    kind: ReferenceKind = "id1-long" if edge == "long" else "id1-short"
    try:
        x1, y1, x2, y2 = (float(v) for v in points)
    except ValueError:
        raise ParameterError("--card points must be numbers (photo pixels)") from None
    _, mm = REFERENCE_OBJECTS[kind]
    return (x1, y1, x2, y2, mm or 0.0), kind


def _job_params(args: argparse.Namespace) -> JobParams:
    """Build the job parameters from the command line; --ruler, --card and --roi need exactly one photo."""
    if (args.ruler or args.card or args.roi) and (args.all or len(args.evidence) != 1):
        raise ParameterError("--ruler, --card and --roi describe one photo: use them with exactly one --evidence SHA")
    ruler, reference = _scale_reference(args)
    export = ExportOptions(
        enabled=not args.no_export,
        mirror=not args.no_mirror,
        target_ppi=args.ppi,
        ruler=ruler,
        reference=reference,
    )
    return JobParams(
        args.period,
        args.min_quality,
        args.flip,
        not args.no_crop,
        args.debug,
        export,
        args.minutiae,
        tuple(args.roi) if args.roi else None,
        finger_position=args.finger_position,
        source_agency=args.source_agency,
        options=MethodOptions(channel=args.channel, specular_mask=args.specular_mask),
    )


def _run_job(case: OpenCase, sha: str, signer: Signer, params: JobParams, args: argparse.Namespace) -> bool:
    """Run one job and print its summary; return False when --keep-going skipped a refused photo."""
    try:
        outcome = run_extraction_job(case, sha, signer, params, nfiq2_command=common.nfiq2_command(args))
    except PHOTO_REFUSALS as exc:  # logged as a failed job; store, custody and output errors stop
        if not args.keep_going:
            raise
        common.warn(f"ridge-case: {sha[:12]}: {exc}")
        return False
    common.say(_job_summary(sha, outcome.job_id, outcome.report, len(outcome.outputs)))
    for warning in (outcome.report.get("limits_of_use") or {}).get("warnings", []):
        common.say(f"  outside the limits of use: {warning}")
    export = outcome.report.get("export") or {}
    notice = (export.get("scale") or {}).get("notice")
    if notice:
        common.say(f"  scale notice: {notice}")
    if export.get("resolution_note"):
        common.say(f"  resolution note: {export['resolution_note']}")
    variants = variants_line(outcome.report.get("parameters") or {}, outcome.report.get("measurements") or {})
    if variants:
        common.say(f"  {variants.strip()}")
    return True


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


def add_commands(sub: Any) -> None:
    """Register ``extract`` on the ``ridge-case`` sub-parser."""
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
    p.add_argument(
        "--card",
        nargs=5,
        metavar=("EDGE", "X1", "Y1", "X2", "Y2"),
        help="scale from two points across an ISO/IEC 7810 ID-1 card (bank-card size) in the photo: "
        "EDGE is long (85.60 mm) or short (53.98 mm)",
    )
    p.add_argument(
        "--roi",
        type=int,
        nargs=4,
        metavar=("X", "Y", "W", "H"),
        help="process only this rectangle of the photo (pixels), e.g. one finger of several",
    )
    p.add_argument("--minutiae", action="store_true", help="also store automatic minutiae (unvalidated, M3)")
    p.add_argument(
        "--finger-position",
        type=int,
        default=0,
        metavar="CODE",
        help="finger the photo shows, ANSI/NIST-ITL code 0 (unknown) to 10, recorded as your statement (FR-38)",
    )
    p.add_argument("--source-agency", metavar="TEXT", help="submitting agency, recorded as your statement (FR-38)")
    p.add_argument(
        "--channel",
        choices=CHANNELS,
        default="green",
        help="colour plane the ridge signal is taken from; auto picks the strongest (unvalidated variant, ADR-014)",
    )
    p.add_argument(
        "--specular-mask",
        action="store_true",
        help="exclude specular highlights from the finger area (unvalidated variant, ADR-014)",
    )
    p.add_argument("--nfiq2", type=Path, help="absolute path of the NIST NFIQ 2 executable (indicative score)")
    p.add_argument("--nfiq2-arg", action="append", default=[], help="extra argument for the NFIQ 2 command")
    p.set_defaults(func=cmd_extract)
