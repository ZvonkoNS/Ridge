"""``ridge-case annotate`` / ``annotations`` / ``export-annotated``: the examiner's marks on an output image (FR-55).

ridge-case annotate CASE --job JOB --image SHA --mark X,Y,KIND[,LABEL] [--mark ...] [--note TEXT] [--replaces SEQ]
ridge-case annotations CASE [--job JOB] [--image SHA] [--json]
ridge-case export-annotated CASE SEQ --to FILE.png [--overwrite]

A set is logged as ``examiner.annotation`` and the chain head is signed right after it. Marks are the
examiner's statements; Ridge draws and lists them and never interprets them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.annotation_image import export_annotated
from ridge.case.annotations import KINDS, Annotation, add_annotation, list_annotations
from ridge.case.identity import unlock_identity
from ridge.case.reports import printable
from ridge.case.store import open_case
from ridge.errors import ParameterError


def parse_mark(text: str) -> dict[str, Any]:
    """``X,Y,KIND[,LABEL]`` from the command line into the mark object the record takes."""
    parts = text.split(",", 3)
    if len(parts) < 3 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        raise ParameterError(f"a mark is X,Y,KIND[,LABEL] with KIND one of {', '.join(KINDS)}: {text!r}")
    mark: dict[str, Any] = {"x": int(parts[0]), "y": int(parts[1]), "kind": parts[2].strip()}
    if len(parts) == 4:
        mark["label"] = parts[3]
    return mark


def _line(a: Annotation) -> str:
    signed = f", signed by #{a.signed_seq}" if a.signed_seq is not None else ", not yet signed"
    replaces = f", replaces #{a.replaces}" if a.replaces is not None else ""
    head = f"#{a.seq}  {a.ts_utc}  {printable(a.actor)}  (job {a.job_id}, {a.role} {a.sha256[:12]}{replaces}{signed})"
    marks = [f"    {m.n}: {m.kind} at ({m.x}, {m.y}){'  ' + printable(m.label) if m.label else ''}" for m in a.marks]
    note = [f"    note: {printable(line)}" for line in (a.note or "").splitlines()]
    return "\n".join([head, *marks, *note])


def cmd_annotate(args: argparse.Namespace) -> None:
    """Record an annotation set (logged and signed)."""
    passphrase, keystore = common.read_passphrase(), common.KEYSTORE_FACTORY()
    signer = unlock_identity(args.case.parent, passphrase, keystore)
    marks = [parse_mark(m) for m in args.mark]
    with open_case(args.case, passphrase, keystore) as case:
        a = add_annotation(
            case, signer, job_id=args.job, sha256=args.image, marks=marks, note=args.note, replaces=args.replaces
        )
    common.say(f"annotation set #{a.seq} recorded with {len(a.marks)} marks, signed by entry #{a.signed_seq}")


def cmd_annotations(args: argparse.Namespace) -> None:
    """List the annotation sets of a case, one job or one image."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        image = case.item(args.image).sha256 if args.image else None
        sets = list_annotations(case.entries, job_id=args.job, sha256=image)
    if args.json:
        common.say(json.dumps([a.to_json() for a in sets], ensure_ascii=False, indent=2), lines=True)
        return
    common.say("\n".join(_line(a) for a in sets) if sets else "no annotations", lines=True)


def cmd_export_annotated(args: argparse.Namespace) -> None:
    """Write the annotated image of one set (logged)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        done = export_annotated(case, args.seq, args.to, overwrite=args.overwrite)
    common.say(f"wrote {done.path} ({done.marks} marks), SHA-256 {done.written_sha256}")


def add_commands(sub: Any) -> None:
    """Register the annotation commands on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("annotate", help="record the examiner's marks on a job's output image (logged and signed)")
    p.add_argument("case", type=Path)
    p.add_argument("--job", required=True)
    p.add_argument("--image", required=True, metavar="SHA", help="the print or comparison export of that job")
    p.add_argument("--mark", action="append", required=True, metavar="X,Y,KIND[,LABEL]", help="one mark; repeat")
    p.add_argument("--note", help="a note on the set")
    p.add_argument(
        "--replaces", type=int, metavar="SEQ", help="the earlier set this one supersedes (it stays in the log)"
    )
    p.set_defaults(func=cmd_annotate)
    p = sub.add_parser("annotations", help="list the examiner's annotation sets")
    p.add_argument("case", type=Path)
    p.add_argument("--job")
    p.add_argument("--image", metavar="SHA")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_annotations)
    p = sub.add_parser("export-annotated", help="write an output image with one set's marks drawn on it (logged)")
    p.add_argument("case", type=Path)
    p.add_argument("seq", type=int, help="the set's custody entry number")
    p.add_argument("--to", type=Path, required=True, metavar="FILE.png")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_export_annotated)
