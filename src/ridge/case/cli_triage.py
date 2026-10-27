"""``ridge-case triage``: which photos of a folder show a measurable ridge pattern (PRD FR-57).

ridge-case triage FOLDER [--to INDEX.csv] [--recursive] [--max-files N] [--json]

Every photo is read once, read-only, and nothing is written next to the photos; the index is a new
file where the examiner says. The order is a reading order for the examiner, not a quality judgement
of any print, and it says nothing about identification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.triage import DEFAULT_MAX_FILES, row_text, run_triage, triage_text


def cmd_triage(args: argparse.Namespace) -> None:
    """Check every photo of the folder, list them in reading order and write the index when asked."""
    triage, written = run_triage(args.folder, recursive=args.recursive, max_files=args.max_files, dest=args.to)
    if args.json:
        common.say(json.dumps(triage.to_json(index=written), ensure_ascii=True, indent=2), lines=True)  # ASCII only
        return
    if written is None:
        for order, row in enumerate(triage.rows, start=1):
            common.say(row_text(order, row))
    for line in triage_text(triage, index=written):
        common.say(line)


def add_commands(sub: Any) -> None:
    """Register ``triage`` on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("triage", help="list the photos of a folder with a measurable ridge pattern first (read-only)")
    p.add_argument("folder", type=Path, help="a folder of photos; nothing in it is changed or written")
    p.add_argument("--to", type=Path, help="write the index as a new .csv file outside the folder")
    p.add_argument("--recursive", action="store_true", help="include subfolders (never through links)")
    p.add_argument(
        "--max-files", type=int, default=DEFAULT_MAX_FILES, help=f"refuse larger folders (default {DEFAULT_MAX_FILES})"
    )
    p.add_argument("--json", action="store_true", help="print the record (ridge.triage/1) as JSON")
    p.set_defaults(func=cmd_triage)
