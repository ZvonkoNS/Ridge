"""``ridge-case metadata``: the photo metadata of one stored evidence or reference image, without a job (FR-36).

ridge-case metadata CASE SHA [--json]

The metadata is read from the verified copy in the case store, never from the source file, and
the read is logged (``evidence.read`` or ``reference.read``), as the sidecar's ``metadata.get`` is.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ridge.case import cli_common as common
from ridge.case.metadata_render import metadata_text
from ridge.case.photo_metadata import read_photo_metadata
from ridge.case.reports import printable
from ridge.case.store import open_case
from ridge.metadata.values import text


def cmd_metadata(args: argparse.Namespace) -> None:
    """Print an imported photo's metadata, read from its verified stored bytes (the read is logged)."""
    with open_case(args.case, common.read_passphrase(), common.KEYSTORE_FACTORY()) as case:
        item, meta = read_photo_metadata(case, args.sha)  # other roles refused before the read
    if args.json:
        # The values are attacker-controlled; ASCII-only JSON cannot carry a terminal escape (CWE-150).
        common.say(json.dumps(meta, ensure_ascii=True, indent=2))
        return
    # The label is the source file's name: shown like a metadata value, so bidirectional marks are visible.
    common.say(printable(f"{item.role} {item.sha256}  {text(item.label)}"))
    for line in metadata_text(meta):
        common.say(printable(line))


def add_commands(sub: Any) -> None:
    """Register the metadata command on the ``ridge-case`` sub-parser."""
    p = sub.add_parser("metadata", help="show an imported photo's metadata, without a job (the read is logged)")
    p.add_argument("case", type=Path)
    p.add_argument("sha", help="SHA-256 of an evidence or reference image, or its first 8 or more characters")
    p.add_argument("--json", action="store_true", help="print the record (ridge.photo-metadata/1) as JSON")
    p.set_defaults(func=cmd_metadata)
