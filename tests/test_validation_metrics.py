"""Validation-study metrics: hand-checked FMR/FNMR, intervals, rule of 30, score files, CLI."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from ridge.errors import InputRejectedError, ParameterError
from ridge.validation.metrics import Rate, det_curve, equal_error_rate, failure_to_extract, operating_point
from ridge.validation.report import build_report, main, read_scores

GENUINE = [0.9, 0.8, 0.7, 0.6, 0.2]  # one weak genuine comparison
IMPOSTOR = [0.1, 0.2, 0.3, 0.4, 0.65, 0.05, 0.15, 0.25, 0.35, 0.45]  # one strong impostor


def test_operating_point_by_hand() -> None:
    point = operating_point(GENUINE, IMPOSTOR, target_fmr=0.1)
    # Lowest threshold with FMR <= 10 %: 0.6 accepts only the 0.65 impostor (1/10) and rejects 0.2 (1/5).
    assert point.threshold == 0.6
    assert (point.fmr.errors, point.fmr.trials) == (1, 10)
    assert (point.fnmr.errors, point.fnmr.trials) == (1, 5)
    assert point.supported is False  # 30 / 0.1 = 300 impostor comparisons needed


def test_strict_target_moves_above_every_impostor() -> None:
    point = operating_point(GENUINE, IMPOSTOR, target_fmr=0.01)
    assert point.fmr.errors == 0
    assert point.threshold > max(IMPOSTOR)
    assert point.fnmr.errors == 2  # 0.6 and 0.2 now rejected


def test_rule_of_30() -> None:
    rng = np.random.default_rng(3)
    impostor = rng.normal(0.2, 0.1, 30_000).tolist()
    genuine = rng.normal(0.8, 0.1, 500).tolist()
    assert operating_point(genuine, impostor, 0.001).supported is True
    assert operating_point(genuine, impostor, 0.0001).supported is False


def test_wilson_interval() -> None:
    low, high = Rate(1, 10).wilson()
    assert low == pytest.approx(0.0179, abs=1e-3)
    assert high == pytest.approx(0.4042, abs=1e-3)
    zero_low, zero_high = Rate(0, 100).wilson()
    assert zero_low == 0.0
    assert 0.0 < zero_high < 0.05


def test_eer_and_det_curve() -> None:
    eer, threshold = equal_error_rate(GENUINE, IMPOSTOR)
    assert 0.0 <= eer <= 0.3
    assert min(GENUINE) <= threshold <= max(IMPOSTOR) + 1
    curve = det_curve(GENUINE, IMPOSTOR, max_points=5)
    assert len(curve) == 5
    fmrs = [fmr for _, fmr, _ in curve]
    assert fmrs == sorted(fmrs, reverse=True)  # FMR falls as the threshold rises


def test_large_inputs_are_fast() -> None:
    rng = np.random.default_rng(5)
    impostor = rng.normal(0.2, 0.1, 1_000_000).tolist()
    genuine = rng.normal(0.8, 0.1, 10_000).tolist()
    start = time.perf_counter()
    operating_point(genuine, impostor, 0.0001)
    equal_error_rate(genuine, impostor)
    assert time.perf_counter() - start < 20


@pytest.mark.parametrize(
    ("genuine", "impostor", "target"),
    [([], [0.1], 0.1), ([0.5], [float("nan")], 0.1), ([0.5], [0.1], 0.0), ([0.5], [0.1], 1.0)],
)
def test_invalid_inputs(genuine: list[float], impostor: list[float], target: float) -> None:
    with pytest.raises(ParameterError):
        operating_point(genuine, impostor, target)


def test_failure_to_extract() -> None:
    assert failure_to_extract(400, 12).value == pytest.approx(0.03)
    with pytest.raises(ParameterError):
        failure_to_extract(10, 11)


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_score_file_with_groups(tmp_path: Path) -> None:
    rows = ["probe,reference,genuine,score,group"]
    rows += [f"p{i},r{i},1,{s},{'A' if i % 2 else 'B'}" for i, s in enumerate(GENUINE)]
    rows += [f"q{i},r{i},0,{s},{'A' if i % 2 else 'B'}" for i, s in enumerate(IMPOSTOR)]
    scores = read_scores(write_csv(tmp_path / "s.csv", rows))
    assert set(scores) == {"all", "A", "B"}
    report = build_report(scores, [0.1], (100, 4))
    assert report["schema"] == "ridge.validation/1"
    assert report["overall"]["genuine_comparisons"] == 5
    assert set(report["groups"]) == {"A", "B"}
    assert report["failure_to_extract"]["value"] == pytest.approx(0.04)


@pytest.mark.parametrize(
    "rows",
    [
        ["genuine,value", "1,0.5"],
        ["genuine,score", "2,0.5"],
        ["genuine,score", "1,abc"],
        ["genuine,score", "1,inf"],
        ["genuine,score", "1,0.5", "1,0.6"],  # no impostors
    ],
)
def test_malformed_score_files(tmp_path: Path, rows: list[str]) -> None:
    with pytest.raises(ParameterError):
        read_scores(write_csv(tmp_path / "bad.csv", rows))


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rows = ["genuine,score"] + [f"1,{s}" for s in GENUINE] + [f"0,{s}" for s in IMPOSTOR]
    scores = write_csv(tmp_path / "s.csv", rows)
    out = tmp_path / "report.json"
    assert main([str(scores), "--fmr", "0.1", "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["overall"]["operating_points"][0]["threshold"] == 0.6
    assert main([str(scores), "-o", str(out)]) == 1  # never overwrites a report
    assert main([str(scores)]) == 0
    assert '"schema": "ridge.validation/1"' in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main([str(scores), "--ftx-attempts", "10"])


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (["genuine,score,group", "1,0.9,all", "0,0.1,all"], "reserved"),
        (["genuine,score,group", "1,0.9, ALL ", "0,0.1,A"], "reserved"),
        (["genuine,score,group", "1,0.9,A", "0,0.1,A", "1,0.8,B"], "B need both"),
        (["genuine,score,group", "1,0.9,A", "0,0.1,"], "group is empty"),
        (["genuine,score", "1," + "9" * 200_000, "0,0.1"], "not valid CSV"),
    ],
)
def test_group_rules_and_csv_errors(tmp_path: Path, rows: list[str], message: str) -> None:
    with pytest.raises(ParameterError, match=message):
        read_scores(write_csv(tmp_path / "bad.csv", rows))


def test_score_file_must_be_bounded_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ridge.validation import report  # noqa: PLC0415

    path = tmp_path / "s.csv"
    path.write_bytes(b"genuine,score\n1,0.9\n0,\xff\n")
    with pytest.raises(ParameterError, match="UTF-8"):
        read_scores(path)
    monkeypatch.setattr(report, "MAX_FILE_BYTES", 8)
    with pytest.raises(InputRejectedError):
        read_scores(path)
