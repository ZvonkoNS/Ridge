"""``ridge-case check-photo``: the capture check (FR-54), before import or on a stored photo.

ridge-case check-photo FILE [--json]                 a photo file, read once, read-only, nothing written
ridge-case check-photo --case CASE SHA [--json]      a stored evidence or reference image (the read is logged)

The check says whether photographing the finger again would help; it is not a quality score of a
print and says nothing about identification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ridge.capture import CaptureCheck, check_file, check_text
from ridge.case import cli_common as common
from ridge.case.capture_check import check_stored_photo
from ridge.case.reports import printable
from ridge.case.store import open_case


def cmd_check(args: argparse.Namespace) -> None:
    """Run the capture check on a file or on a stored photo and print the findings."""
    if args.case is None:
        check = check_file(Path(args.target))
        heading = None
    else:
        with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
            item, check = check_stored_photo(case, args.target)
        heading = f"{item.role} {item.sha256}  {item.label}"
    _print(check, heading, as_json=args.json)


def _print(check: CaptureCheck, heading: str | None, *, as_json: bool) -> None:
    if as_json:
        common.say(json.dumps(check.to_json(), ensure_ascii=True, indent=2), lines=True)  # ASCII: no terminal escapes
        return
    if heading is not None:
        common.say(printable(heading))  # the label is the source file's name: shown like a metadata value
    for line in check_text(check):
        common.say(printable(line))


def add_commands(sub: Any) -> None:
    """Register the capture-check command on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("check-photo", help="say whether a photo of a finger should be taken again (indicative)")
    p.add_argument("target", help="a photo file, or with --case the SHA-256 of a stored photo (8 or more characters)")
    p.add_argument("--case", type=Path, help="check a stored evidence or reference image of this case (logged read)")
    p.add_argument("--json", action="store_true", help="print the record (ridge.capture-check/1) as JSON")
    p.set_defaults(func=cmd_check)
