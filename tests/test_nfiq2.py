"""NFIQ 2 adapter (PRD FR-33) against a FAKE nfiq2: a Python script written to tmp_path.

The real NIST tool is never needed or run here. The fake checks that it was handed a PNG,
records where the copy was and then behaves as configured (score, CSV, garbage, exit code,
sleep, flood of output).
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from ridge.errors import ParameterError, QualityToolError
from ridge.export import encode_png
from ridge.quality import Nfiq2, Nfiq2NotComputed, Nfiq2Result, parse_score
from ridge.quality.nfiq2 import DEFAULT_TIMEOUT_S, MAX_OUTPUT_BYTES, PNG_SIGNATURE

PNG = encode_png(np.full((32, 32), 200, np.uint8), 500.0)
CSV_HEADER = '"Filename","FingerCode","QualityScore","OptionalError","Quantized","Resampled"'

FAKE = """\
import pathlib
import sys
import time

args = sys.argv[1:]
if args[-1:] == ["--version"]:
    sys.stdout.write({version!r})
    sys.exit({version_code!r})
image = pathlib.Path(args[-1])
mode = oct(image.stat().st_mode & 0o777)
pathlib.Path({seen!r}).write_text(str(image) + "\\n" + mode, encoding="utf-8")
if not image.read_bytes().startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
    sys.exit(9)
time.sleep({sleep!r})
sys.stdout.write({stdout!r} * {repeat!r})
sys.exit({code!r})
"""


@dataclass(frozen=True)
class Fake:
    tool: Nfiq2
    script: Path
    seen: Path  # the fake writes the path (and mode) of the image copy it was given here
    work: Path  # work_dir: must be empty again after every call

    def seen_image(self) -> Path:
        return Path(self.seen.read_text(encoding="utf-8").splitlines()[0])

    def assert_cleaned_up(self) -> None:
        assert list(self.work.iterdir()) == []


def make_fake(
    tmp_path: Path,
    *,
    stdout: str = "54\n",
    code: int = 0,
    sleep: float = 0.0,
    repeat: int = 1,
    version: str = "NFIQ2 Version: 2.3.0\nFingerJet Version: 5.2.1\n",
    version_code: int = 0,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Fake:
    script, seen, work = tmp_path / "fake_nfiq2.py", tmp_path / "seen.txt", tmp_path / "work"
    work.mkdir()
    fields = {"stdout": stdout, "code": code, "sleep": sleep, "repeat": repeat, "seen": str(seen)}
    script.write_text(FAKE.format(version=version, version_code=version_code, **fields), encoding="utf-8")
    tool = Nfiq2([sys.executable, str(script)], timeout_s, work_dir=work)
    return Fake(tool=tool, script=script, seen=seen, work=work)


def not_computed(fake: Fake) -> str:
    outcome = fake.tool.assess(PNG)
    assert isinstance(outcome, Nfiq2NotComputed)
    with pytest.raises(QualityToolError) as excinfo:
        fake.tool.score(PNG)
    assert str(excinfo.value) == outcome.reason
    fake.assert_cleaned_up()
    return outcome.reason


# ----------------------------------------------------------------------------- scores


def test_plain_integer_score(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, stdout="  54  \n")
    result = fake.tool.score(PNG)
    assert result == Nfiq2Result(score=54, version="NFIQ2 Version: 2.3.0", raw_exit_code=0)
    image = fake.seen_image()
    assert image.parent.parent.resolve() == fake.work.resolve()  # copy was inside work_dir
    assert image.suffix == ".png"
    assert not image.exists()
    fake.assert_cleaned_up()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_image_copy_is_private(tmp_path: Path) -> None:
    fake = make_fake(tmp_path)
    fake.tool.score(PNG)
    assert fake.seen.read_text(encoding="utf-8").splitlines()[1] == "0o600"


def test_csv_score(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, stdout=f'{CSV_HEADER}\n"export.png",0,61,NA,0,0\n')
    outcome = fake.tool.assess(PNG)
    assert isinstance(outcome, Nfiq2Result)
    assert outcome.score == 61
    fake.assert_cleaned_up()


@pytest.mark.parametrize(
    ("stdout", "reason"),
    [
        ("Error: could not read image\n", "NFIQ 2 output was not understood"),
        ("", "NFIQ 2 output was not understood"),
        ("Warning: not 500 PPI\n54\n", "NFIQ 2 output was not understood"),
        ("101\n", "NFIQ 2 reported 101, outside the score range 0..100"),
        (f'{CSV_HEADER}\n"export.png",0,255,"Error",0,0\n', "NFIQ 2 reported 255, outside the score range 0..100"),
    ],
    ids=["garbage", "empty", "extra-line", "out-of-range", "csv-error-value"],
)
def test_unusable_output_is_not_computed(tmp_path: Path, stdout: str, reason: str) -> None:
    fake = make_fake(tmp_path, stdout=stdout)
    assert not_computed(fake) == reason


def test_non_zero_exit_is_not_computed(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, stdout="54\n", code=3)
    assert not_computed(fake) == "NFIQ 2 exited with code 3"


def test_timeout_is_not_computed(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, sleep=60.0, timeout_s=1.0)
    start = time.monotonic()
    outcome = fake.tool.assess(PNG)
    assert time.monotonic() - start < 30.0
    assert outcome == Nfiq2NotComputed(reason="NFIQ 2 did not finish within 1 s")
    assert str(outcome) == "not computed: NFIQ 2 did not finish within 1 s"
    fake.assert_cleaned_up()


def test_oversized_output_is_refused(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, stdout="1", repeat=2 * MAX_OUTPUT_BYTES)
    assert not_computed(fake) == "NFIQ 2 printed more than 1024 KiB"


def test_missing_tool_is_not_computed(tmp_path: Path) -> None:
    tool = Nfiq2([str(tmp_path / "NFIQ2" / "bin" / "nfiq2.exe")], work_dir=tmp_path)
    outcome = tool.assess(PNG)
    assert outcome == Nfiq2NotComputed(reason="NFIQ 2 is not installed at the configured path")
    assert tool.version() is None
    assert list(tmp_path.iterdir()) == []  # nothing was written


def test_tool_that_cannot_start_is_not_computed(tmp_path: Path) -> None:
    not_a_program = tmp_path / "nfiq2.txt"
    not_a_program.write_text("not an executable\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    outcome = Nfiq2([str(not_a_program)], work_dir=work).assess(PNG)
    assert isinstance(outcome, Nfiq2NotComputed)
    assert outcome.reason.startswith("NFIQ 2 could not be started (")
    assert list(work.iterdir()) == []


# ----------------------------------------------------------------------------- version


def test_version_is_sanitised_and_asked_once(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, version="\n\x1b[31mNFIQ2\x07 2.3.0\x1b[0m\r\nmore\n")
    assert fake.tool.version() == "[31mNFIQ2 2.3.0[0m"  # control characters removed (CWE-150)
    fake.script.unlink()
    assert fake.tool.version() == "[31mNFIQ2 2.3.0[0m"  # cached, not asked again


@pytest.mark.parametrize(("version", "version_code"), [("NFIQ2 2.3.0\n", 2), ("", 0), ("\x1b\x07\n", 0)])
def test_unknown_version_does_not_block_the_score(tmp_path: Path, version: str, version_code: int) -> None:
    fake = make_fake(tmp_path, version=version, version_code=version_code)
    assert fake.tool.score(PNG) == Nfiq2Result(score=54, version=None, raw_exit_code=0)


def test_long_version_is_truncated(tmp_path: Path) -> None:
    fake = make_fake(tmp_path, version="v" * 500 + "\n")
    assert fake.tool.version() == "v" * 100


# ----------------------------------------------------------------------------- configuration


def test_command_and_default_timeout(tmp_path: Path) -> None:
    tool = Nfiq2([sys.executable, "-I"], work_dir=tmp_path)
    assert tool.command == (sys.executable, "-I")
    assert DEFAULT_TIMEOUT_S == 60.0


@pytest.mark.parametrize(
    "command",
    [
        ["nfiq2"],  # bare name: would need a PATH lookup
        ["bin/nfiq2.exe"],
        [""],
        [],
        "C:/NFIQ2/bin/nfiq2.exe",  # a string, not an argv list
        [sys.executable, 3],
        [sys.executable, "a\0b"],
        [b"/usr/bin/nfiq2"],
    ],
    ids=["bare", "relative", "empty-path", "empty", "string", "non-string", "nul", "bytes"],
)
def test_bad_command_is_rejected(tmp_path: Path, command: object) -> None:
    with pytest.raises(ParameterError):
        Nfiq2(cast(list[str], command), work_dir=tmp_path)


@pytest.mark.parametrize("timeout_s", [0, -1.0, math.nan, math.inf, 3601.0, True, "60"], ids=repr)
def test_bad_timeout_is_rejected(tmp_path: Path, timeout_s: object) -> None:
    with pytest.raises(ParameterError):
        Nfiq2([sys.executable], cast(float, timeout_s), work_dir=tmp_path)


def test_work_dir_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ParameterError):
        Nfiq2([sys.executable], work_dir=tmp_path / "missing")


@pytest.mark.parametrize(
    "png_bytes", [b"", b"GIF89a" + PNG[6:], bytearray(PNG), "not bytes"], ids=["empty", "gif", "bytearray", "str"]
)
def test_input_must_be_png_bytes(tmp_path: Path, png_bytes: object) -> None:
    fake = make_fake(tmp_path)
    with pytest.raises(ParameterError):
        fake.tool.assess(cast(bytes, png_bytes))
    assert not fake.seen.exists()  # the tool never ran


def test_oversized_png_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ridge.quality.nfiq2.MAX_IMAGE_BYTES", len(PNG) - 1)
    with pytest.raises(ParameterError):
        Nfiq2([sys.executable], work_dir=tmp_path).score(PNG)


# ----------------------------------------------------------------------------- parser


@pytest.mark.parametrize(
    ("stdout", "score"),
    [
        (b"0", 0),
        (b"100\r\n", 100),
        (b"\n  7 \n\n", 7),
        (b"054\n", 54),
        (b"Filename,QualityScore\nx.png,42\n", 42),
        (b'"Filename","QualityScore","OptionalError"\r\n"x.png", 42 ,NA\r\n', 42),
    ],
)
def test_parse_score_accepts(stdout: bytes, score: int) -> None:
    assert parse_score(stdout) == score


@pytest.mark.parametrize(
    "stdout",
    [
        b"",
        b"-1",
        b"1e2",
        b"54 55",
        b"0054",
        b"54.0",
        b"54\n55\n56\n",
        b"Filename,Score\nx.png,42\n",  # no QualityScore column
        b"QualityScore,QualityScore\n1,2\n",  # ambiguous
        b"Filename,QualityScore\nx.png\n",  # row shorter than header
        b"Filename,QualityScore\nx.png,NA\n",
        b'"Filename"x,QualityScore\nx.png,42\n',  # malformed quoting
        pytest.param(b"Filename,QualityScore\n" + b"x" * 200_000 + b",42\n", id="field-over-csv-size-limit"),
        "\u0665\u0664".encode(),  # Arabic-Indic digits: int() would accept them
        b"\xff\xfe5\x004\x00",
    ],
)
def test_parse_score_refuses(stdout: bytes) -> None:
    with pytest.raises(QualityToolError):
        parse_score(stdout)


def test_endless_output_is_cut_off_while_running(tmp_path: Path) -> None:
    """The tool is killed as soon as it passes the output cap, long before the timeout."""
    script = tmp_path / "flood.py"
    script.write_text("import sys\nwhile True:\n    sys.stdout.write('1' * 65536)\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    tool = Nfiq2([sys.executable, str(script)], timeout_s=60.0, work_dir=work)
    start = time.perf_counter()
    with pytest.raises(QualityToolError, match="printed more than"):
        tool.score(PNG_SIGNATURE + b"x" * 100)
    assert time.perf_counter() - start < 30
