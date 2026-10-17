"""``ridge-case`` comparison commands (FR-52): reference images and equal-scale comparison sheets.

    ridge-case import-reference CASE candidate.png --source "NAFIS candidate 3"
    ridge-case compare CASE EXPORT_SHA REFERENCE_SHA --to sheet.png [--reference-ppi 500] [--ppi 500]

View aid only: Ridge never aligns, matches or scores.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.compare import SHEET_PPI, export_sheet
from ridge.case.store import open_case


def cmd_import_reference(args: argparse.Namespace) -> None:
    """Import NAFIS/AFIS candidate images for side-by-side viewing (never processed)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        for path in args.files:
            item = case.import_reference(path, args.source)
            common.say(f"{path} -> reference {item.sha256}  ({item.size} bytes)")


def cmd_compare(args: argparse.Namespace) -> None:
    """Write a side-by-side sheet of an export and a reference at equal scale (logged)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        sheet = export_sheet(
            case,
            args.export,
            args.reference,
            args.to,
            reference_ppi=args.reference_ppi,
            ppi=args.ppi,
            overwrite=args.overwrite,
        )
    common.say(
        f"comparison sheet {sheet.sha256[:12]} written to {args.to} at {sheet.ppi:g} ppi "
        f"(reference {sheet.reference_ppi:g} ppi from {sheet.reference_ppi_source}); view aid only, no matching"
    )


def add_commands(sub: Any) -> None:
    """Register the comparison commands on the ``ridge-case`` sub-parser."""
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
