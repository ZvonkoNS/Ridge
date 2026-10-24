"""``ridge-case sweep``: rescaled copies of a comparison export over its scale uncertainty (PRD FR-39).

ridge-case sweep CASE SHA --to NEW_FOLDER [--steps 3|5|7|9] [--format png|tiff|bmp]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.store import open_case
from ridge.case.sweep import INDEX, export_sweep
from ridge.export.formats import FORMATS
from ridge.export.sweep import DEFAULT_STEPS


def cmd_sweep(args: argparse.Namespace) -> None:
    """Write the scale sweep of one export into a new folder (every file logged)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        sweep = export_sweep(case, args.case.parent, args.sha, args.to, steps=args.steps, fmt=args.format)
    factors = ", ".join(f"{f.factor:.4f}" for f in sweep.files)
    common.say(
        f"{len(sweep.files)} file(s) written to {args.to} at factors {factors} (scale {sweep.scale.get('method')}, "
        f"+-{sweep.scale.get('uncertainty_pct')} %), listed in {INDEX}; each is in the custody log"
    )
    common.say("submit them as separate searches; the files are rescaled copies, not new evidence")


def add_commands(sub: Any) -> None:
    """Register ``sweep`` on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("sweep", help="rescaled copies of an export over its scale uncertainty, for AFIS searches")
    p.add_argument("case", type=Path)
    p.add_argument("sha", help="a comparison export (export or export-gray) by SHA-256")
    p.add_argument("--to", type=Path, required=True, help="a folder that does not exist yet")
    p.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="odd number of factors, 3 to 9 (default 3)")
    p.add_argument("--format", choices=FORMATS, help="file format (default png; tiff and bmp are uncompressed)")
    p.set_defaults(func=cmd_sweep)
