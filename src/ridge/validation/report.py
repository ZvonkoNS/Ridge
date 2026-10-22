"""``ridge-validate``: score file -> validation metrics report (JSON) for the validation study.

    ridge-validate scores.csv --fmr 0.001 --fmr 0.0001 --ftx-attempts 400 --ftx-failures 12 -o report.json

``scores.csv`` (from the lab's matcher run; never committed) has a header row with at least
``genuine`` (1 same finger, 0 different fingers) and ``score`` columns; an optional ``group``
column (e.g. skin-tone or capture-condition category) adds a per-group breakdown, which the
PRD requires as a bias check. Other columns are ignored. Rows are validated strictly: with a
``group`` column every row needs a group, ``all`` is reserved for the overall population, and
every group needs both genuine and impostor comparisons, so no group can drop out of the bias
check unnoticed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ridge.errors import ParameterError, RidgeError
from ridge.image_io import MiB, publish, read_bounded
from ridge.terminal import safe
from ridge.validation.metrics import det_curve, equal_error_rate, failure_to_extract, operating_point

SCHEMA = "ridge.validation/1"
MAX_FILE_BYTES = 512 * MiB
MAX_GROUPS = 50

type Scores = dict[str, tuple[list[float], list[float]]]  # group -> (genuine, impostor)


def read_scores(path: Path) -> Scores:
    """Parse a score CSV into per-group genuine/impostor lists ('all' holds every row)."""
    data = read_bounded(path, MAX_FILE_BYTES)  # regular files only, size checked while reading (CWE-400)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ParameterError("the score file is not UTF-8 text") from None
    try:
        return _parse(csv.DictReader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise ParameterError(f"the score file is not valid CSV: {exc}") from None


def _parse(reader: csv.DictReader[str]) -> Scores:
    if reader.fieldnames is None or not {"genuine", "score"} <= set(reader.fieldnames):
        raise ParameterError("the score file needs a header with 'genuine' and 'score' columns")
    grouped = "group" in reader.fieldnames
    groups: Scores = defaultdict(lambda: ([], []))
    for line, row in enumerate(reader, start=2):
        genuine, score = (row.get("genuine") or "").strip(), (row.get("score") or "").strip()
        if genuine not in ("0", "1"):
            raise ParameterError(f"line {line}: genuine must be 0 or 1")
        try:
            value = float(score)
        except ValueError:
            raise ParameterError(f"line {line}: score is not a number") from None
        if not math.isfinite(value):
            raise ParameterError(f"line {line}: score must be finite")
        names = ["all"]
        if grouped:
            group = (row.get("group") or "").strip()
            if not group:
                raise ParameterError(f"line {line}: group is empty (every row needs one for the bias check)")
            if group.casefold() == "all":
                raise ParameterError(f"line {line}: the group name 'all' is reserved for the overall population")
            names.append(group)
        for name in names:
            groups[name][0 if genuine == "1" else 1].append(value)
        if len(groups) > MAX_GROUPS + 1:
            raise ParameterError(f"more than {MAX_GROUPS} groups")
    if "all" not in groups or not groups["all"][0] or not groups["all"][1]:
        raise ParameterError("the score file needs both genuine (1) and impostor (0) comparisons")
    incomplete = sorted(name for name, (g, i) in groups.items() if not (g and i))
    if incomplete:
        raise ParameterError(f"group(s) {', '.join(incomplete)} need both genuine and impostor comparisons")
    return dict(groups)


def summarise(genuine: list[float], impostor: list[float], targets: Sequence[float]) -> dict[str, Any]:
    """Metrics for one group."""
    eer, eer_threshold = equal_error_rate(genuine, impostor)
    return {
        "genuine_comparisons": len(genuine),
        "impostor_comparisons": len(impostor),
        "operating_points": [operating_point(genuine, impostor, t).to_json() for t in targets],
        "eer": {"value": eer, "threshold": eer_threshold},
    }


def build_report(scores: Scores, targets: Sequence[float], ftx: tuple[int, int] | None) -> dict[str, Any]:
    """Build the full validation metrics report."""
    genuine, impostor = scores["all"]
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "method": "ISO/IEC 19795-1 style verification metrics; Wilson 95 % intervals assume independent comparisons",
        "overall": summarise(genuine, impostor, targets),
        "det_curve": [{"threshold": t, "fmr": a, "fnmr": b} for t, a, b in det_curve(genuine, impostor)],
        "groups": {name: summarise(g, i, targets) for name, (g, i) in sorted(scores.items()) if name != "all"},
    }
    if ftx is not None:
        report["failure_to_extract"] = failure_to_extract(*ftx).to_json()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``ridge-validate``."""
    ap = argparse.ArgumentParser(prog="ridge-validate", description=__doc__.splitlines()[0])
    ap.add_argument("scores", type=Path, help="score CSV from the matcher run")
    ap.add_argument("--fmr", type=float, action="append", help="target FMR (repeatable; default 0.001 and 0.0001)")
    ap.add_argument("--ftx-attempts", type=int, help="validation photos processed")
    ap.add_argument("--ftx-failures", type=int, help="photos without a usable export")
    ap.add_argument("-o", "--out", type=Path, help="write the JSON report here (refuses to overwrite)")
    args = ap.parse_args(argv)
    if (args.ftx_attempts is None) != (args.ftx_failures is None):
        ap.error("--ftx-attempts and --ftx-failures go together")
    try:
        ftx = None if args.ftx_attempts is None else (args.ftx_attempts, args.ftx_failures)
        report = build_report(read_scores(args.scores), args.fmr or [0.001, 0.0001], ftx)
        text = json.dumps(report, indent=2, allow_nan=False)
        if args.out:
            publish(args.out, text.encode("utf-8"))
        else:
            print(text)  # noqa: T201
    except (RidgeError, OSError) as exc:
        print(safe(f"ridge-validate: {exc}"), file=sys.stderr)  # noqa: T201
        return 1
    return 0
