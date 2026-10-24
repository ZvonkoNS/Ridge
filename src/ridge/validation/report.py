"""``ridge-validate``: matcher results -> validation metrics report (JSON) for the validation study.

    ridge-validate scores.csv --fmr 0.001 --fmr 0.0001 --ftx-attempts 400 --ftx-failures 12 -o report.json
    ridge-validate --ranks ranks.csv --rank 1 --rank 10 -o report.json      (1:N searches, as an AFIS runs them)
    ridge-validate scores.csv --ranks ranks.csv -o report.json               (both)

``scores.csv`` (from the lab's matcher run; never committed) has a header row with at least
``genuine`` (1 same finger, 0 different fingers) and ``score`` columns; an optional ``group``
column (e.g. skin-tone or capture-condition category) adds a per-group breakdown, which the
PRD requires as a bias check. Other columns are ignored. Rows are validated strictly: with a
``group`` column every row needs a group, ``all`` is reserved for the overall population, and
every group needs both genuine and impostor comparisons, so no group can drop out of the bias
check unnoticed.

``ranks.csv`` (one row per 1:N search of a Ridge export against a gallery holding the mate)
has ``probe`` and ``rank`` columns: the rank of the mate in the candidate list (1 = first),
empty when the mate was not returned; the same optional ``group`` column applies. It gives the
rank-k hit rates and the CMC curve, the metrics an AFIS search is judged by (FR-43).
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
from ridge.validation.metrics import (
    MAX_RANK,
    cmc_curve,
    det_curve,
    equal_error_rate,
    failure_to_extract,
    hit_rate,
    not_returned,
    operating_point,
)

SCHEMA = "ridge.validation/1"
MAX_FILE_BYTES = 512 * MiB
MAX_GROUPS = 50
MAX_CMC_RANK = 200  # the curve is thinned to the ranks an operator reviews
DEFAULT_RANKS = (1, 5, 10, 20)
METHOD = (
    "ISO/IEC 19795-1 style metrics: verification (FMR/FNMR, DET, EER) from comparison scores and "
    "identification (rank-k hit rate, CMC) from 1:N search ranks; Wilson 95 % intervals assume "
    "independent comparisons"
)

type Scores = dict[str, tuple[list[float], list[float]]]  # group -> (genuine, impostor)
type Ranks = dict[str, list[int | None]]  # group -> rank of the mate per probe (None: not returned)


def read_scores(path: Path) -> Scores:
    """Parse a score CSV into per-group genuine/impostor lists ('all' holds every row)."""
    try:
        return _parse(csv.DictReader(io.StringIO(_text(path), newline="")))
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


def _text(path: Path) -> str:
    data = read_bounded(path, MAX_FILE_BYTES)  # regular files only, size checked while reading (CWE-400)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ParameterError(f"{path.name} is not UTF-8 text") from None


def _group_of(row: dict[str, str], line: int, grouped: bool) -> list[str]:
    names = ["all"]
    if grouped:
        group = (row.get("group") or "").strip()
        if not group:
            raise ParameterError(f"line {line}: group is empty (every row needs one for the bias check)")
        if group.casefold() == "all":
            raise ParameterError(f"line {line}: the group name 'all' is reserved for the overall population")
        names.append(group)
    return names


def read_ranks(path: Path) -> Ranks:
    """Parse a rank CSV into per-group lists of mate ranks ('all' holds every row; None = not returned)."""
    try:
        reader = csv.DictReader(io.StringIO(_text(path), newline=""))
        if reader.fieldnames is None or not {"probe", "rank"} <= set(reader.fieldnames):
            raise ParameterError("the rank file needs a header with 'probe' and 'rank' columns")
        grouped = "group" in reader.fieldnames
        groups: Ranks = defaultdict(list)
        for line, row in enumerate(reader, start=2):
            if (
                row.get("rank") is None or None in row
            ):  # csv fills a short row with None and keeps extra fields under None
                raise ParameterError(f"line {line}: the row does not have the header's fields")
            if not (row.get("probe") or "").strip():
                raise ParameterError(f"line {line}: probe is empty")
            text = (row.get("rank") or "").strip()
            rank = None if text == "" else _rank_value(text, line)
            for name in _group_of(row, line, grouped):
                groups[name].append(rank)
            if len(groups) > MAX_GROUPS + 1:
                raise ParameterError(f"more than {MAX_GROUPS} groups")
    except csv.Error as exc:
        raise ParameterError(f"the rank file is not valid CSV: {exc}") from None
    if "all" not in groups:
        raise ParameterError("the rank file holds no searches")
    return dict(groups)


def _rank_value(text: str, line: int) -> int:
    if not text.isdigit() or not 1 <= int(text) <= MAX_RANK:
        raise ParameterError(f"line {line}: rank must be a whole number from 1 to {MAX_RANK}, or empty")
    return int(text)


def summarise_identification(ranks: list[int | None], targets: Sequence[int]) -> dict[str, Any]:
    """Identification metrics for one group: rank-k hit rates and the CMC curve."""
    highest = max(*targets, *(r for r in ranks if r is not None), 1)
    return {
        "probes": len(ranks),
        "not_returned": not_returned(ranks),
        "hit_rates": {str(k): hit_rate(ranks, k).to_json() for k in targets},
        "cmc": [{"rank": k, "hit_rate": v} for k, v in cmc_curve(ranks, min(highest, MAX_CMC_RANK))],
    }


def summarise(genuine: list[float], impostor: list[float], targets: Sequence[float]) -> dict[str, Any]:
    """Metrics for one group."""
    eer, eer_threshold = equal_error_rate(genuine, impostor)
    return {
        "genuine_comparisons": len(genuine),
        "impostor_comparisons": len(impostor),
        "operating_points": [operating_point(genuine, impostor, t).to_json() for t in targets],
        "eer": {"value": eer, "threshold": eer_threshold},
    }


def build_report(
    scores: Scores | None,
    targets: Sequence[float],
    ftx: tuple[int, int] | None,
    ranks: Ranks | None = None,
    rank_targets: Sequence[int] = DEFAULT_RANKS,
) -> dict[str, Any]:
    """Build the validation metrics report from scores (verification), ranks (identification) or both."""
    if scores is None and ranks is None:
        raise ParameterError("give comparison scores, search ranks, or both")
    report: dict[str, Any] = {"schema": SCHEMA, "method": METHOD}
    if scores is not None:
        genuine, impostor = scores["all"]
        report["overall"] = summarise(genuine, impostor, targets)
        report["det_curve"] = [{"threshold": t, "fmr": a, "fnmr": b} for t, a, b in det_curve(genuine, impostor)]
        report["groups"] = {name: summarise(g, i, targets) for name, (g, i) in sorted(scores.items()) if name != "all"}
    if ranks is not None:
        groups = {name: summarise_identification(r, rank_targets) for name, r in sorted(ranks.items()) if name != "all"}
        report["identification"] = {**summarise_identification(ranks["all"], rank_targets), "groups": groups}
    if ftx is not None:
        report["failure_to_extract"] = failure_to_extract(*ftx).to_json()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``ridge-validate``."""
    ap = argparse.ArgumentParser(prog="ridge-validate", description=__doc__.splitlines()[0])
    ap.add_argument("scores", type=Path, nargs="?", help="score CSV from the matcher run (verification)")
    ap.add_argument("--fmr", type=float, action="append", help="target FMR (repeatable; default 0.001 and 0.0001)")
    ap.add_argument("--ranks", type=Path, help="rank CSV from 1:N searches (probe, rank of the mate, optional group)")
    ap.add_argument(
        "--rank", type=int, action="append", help="rank-k hit rate to report (repeatable; default 1, 5, 10, 20)"
    )
    ap.add_argument("--ftx-attempts", type=int, help="validation photos processed")
    ap.add_argument("--ftx-failures", type=int, help="photos without a usable export")
    ap.add_argument("-o", "--out", type=Path, help="write the JSON report here (refuses to overwrite)")
    args = ap.parse_args(argv)
    if (args.ftx_attempts is None) != (args.ftx_failures is None):
        ap.error("--ftx-attempts and --ftx-failures go together")
    if args.scores is None and args.ranks is None:
        ap.error("give a score CSV, --ranks RANKS.csv, or both")
    try:
        ftx = None if args.ftx_attempts is None else (args.ftx_attempts, args.ftx_failures)
        scores = read_scores(args.scores) if args.scores is not None else None
        ranks = read_ranks(args.ranks) if args.ranks is not None else None
        rank_targets = tuple(sorted(set(args.rank))) if args.rank else DEFAULT_RANKS
        report = build_report(scores, args.fmr or [0.001, 0.0001], ftx, ranks, rank_targets)
        text = json.dumps(report, indent=2, allow_nan=False)
        if args.out:
            publish(args.out, text.encode("utf-8"))
        else:
            print(text)  # noqa: T201
    except (RidgeError, OSError) as exc:
        print(safe(f"ridge-validate: {exc}"), file=sys.stderr)  # noqa: T201
        return 1
    return 0
