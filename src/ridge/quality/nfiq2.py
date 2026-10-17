"""Optional NFIQ 2 score of an export via the NIST reference implementation (PRD FR-33).

INDICATIVE ONLY. NFIQ 2 (ISO/IEC 29794-4:2024) is defined for 500 ppi friction-ridge images
from contact capture. Ridge exports are derived from photos, which is outside that scope (an
exception recorded in the project's standards profile): a score on them is not a
standard-conformant quality measurement, says nothing about suitability for identification
and must be labelled indicative wherever it is shown. Thresholds come from validation only.

The NIST tool is an external program that Ridge neither bundles nor downloads. It is
configured as an argv prefix whose first element is the absolute path of the executable:
Ridge never searches PATH and never uses a shell. Each image is handed over as a temporary
file in a new private directory under ``work_dir`` (keep that inside the case or output
area: the copy is biometric data), and the directory is always removed afterwards. The
tool's output is untrusted: it is limited to MAX_OUTPUT_BYTES and parsed strictly.

A missing tool, a timeout, a non-zero exit or output that is not one score in 0..100 is not
a job failure: ``Nfiq2.score`` raises ``QualityToolError`` and ``Nfiq2.assess`` returns
``Nfiq2NotComputed``; the job report records "not computed: <reason>".
"""

from __future__ import annotations

import csv
import math
import os
import re
import subprocess  # one configured tool: argv list, absolute path, no shell  # nosec B404
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ridge.errors import ParameterError, QualityToolError

SCORE_MIN: Final = 0
SCORE_MAX: Final = 100
DEFAULT_TIMEOUT_S: Final = 60.0
MAX_TIMEOUT_S: Final = 3600.0
MAX_OUTPUT_BYTES: Final = 1024 * 1024  # stdout larger than this is refused, not parsed
MAX_IMAGE_BYTES: Final = 256 * 1024 * 1024
MAX_VERSION_CHARS: Final = 100
VERSION_ARGS: Final = ("--version",)
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
SCORE_COLUMN: Final = "QualityScore"  # column name in NFIQ 2's CSV output

_SCORE = re.compile(r"[0-9]{1,3}")
_NOT_UNDERSTOOD = "NFIQ 2 output was not understood"


@dataclass(frozen=True, slots=True)
class Nfiq2Result:
    """An indicative NFIQ 2 score (0..100) with the tool version, when it reported one."""

    score: int
    version: str | None
    raw_exit_code: int


@dataclass(frozen=True, slots=True)
class Nfiq2NotComputed:
    """No score: why, in words that are safe to put in a report (no tool output, no paths)."""

    reason: str

    def __str__(self) -> str:
        return f"not computed: {self.reason}"


def _check_command(command: object) -> tuple[str, ...]:
    if isinstance(command, str | bytes) or not isinstance(command, Sequence) or not command:
        raise ParameterError("the NFIQ 2 command must be a non-empty list of arguments")
    argv = tuple(command)
    if not all(isinstance(arg, str) and "\0" not in arg for arg in argv):
        raise ParameterError("NFIQ 2 command arguments must be strings without NUL characters")
    if not (argv[0] and Path(argv[0]).is_absolute()):
        raise ParameterError("the NFIQ 2 executable must be an absolute path (PATH is never searched)")
    return argv


def _check_timeout(timeout_s: object) -> float:
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, int | float):
        raise ParameterError("timeout_s must be a number of seconds")
    if not (math.isfinite(timeout_s) and 0 < timeout_s <= MAX_TIMEOUT_S):
        raise ParameterError(f"timeout_s must be more than 0 and at most {MAX_TIMEOUT_S:g} seconds")
    return float(timeout_s)


def _check_png(png_bytes: object) -> bytes:
    if not isinstance(png_bytes, bytes) or not png_bytes.startswith(PNG_SIGNATURE):
        raise ParameterError("NFIQ 2 needs the export as PNG bytes")
    if len(png_bytes) > MAX_IMAGE_BYTES:
        raise ParameterError(f"the PNG is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MiB")
    return png_bytes


def _csv_score(header_line: str, row_line: str) -> str:
    try:  # csv.Error: e.g. a field over csv's size limit (output can be up to 1 MiB)
        header = [name.strip() for name in next(csv.reader([header_line], strict=True))]
        row = next(csv.reader([row_line], strict=True))
    except csv.Error as exc:
        raise QualityToolError(_NOT_UNDERSTOOD) from exc
    if header.count(SCORE_COLUMN) != 1 or len(row) != len(header):
        raise QualityToolError(_NOT_UNDERSTOOD)
    return row[header.index(SCORE_COLUMN)].strip()


def parse_score(stdout: bytes) -> int:
    """Parse NFIQ 2 output strictly into a score in 0..100, else raise QualityToolError.

    Accepted: a single line holding the integer score, or a CSV header line containing a
    ``QualityScore`` column followed by exactly one data row. Blank lines and surrounding
    whitespace are ignored; anything else (warnings, several rows, NFIQ 2's error value 255)
    is refused rather than guessed at.
    """
    lines = [line.strip() for line in stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if len(lines) == 1:
        field = lines[0]
    elif len(lines) == 2:
        field = _csv_score(lines[0], lines[1])
    else:
        raise QualityToolError(_NOT_UNDERSTOOD)
    if not _SCORE.fullmatch(field):
        raise QualityToolError(_NOT_UNDERSTOOD)
    value = int(field)
    if not SCORE_MIN <= value <= SCORE_MAX:
        raise QualityToolError(f"NFIQ 2 reported {value}, outside the score range {SCORE_MIN}..{SCORE_MAX}")
    return value


def _version_line(stdout: bytes) -> str | None:
    """First non-empty line, reduced to printable ASCII (no control characters, CWE-150)."""
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        clean = "".join(ch for ch in line if ch.isascii() and ch.isprintable()).strip()
        if clean:
            return clean[:MAX_VERSION_CHARS]
    return None


def _write_private(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as fh:
        fh.write(data)


class Nfiq2:
    """The examiner's installation of the NIST NFIQ 2 command-line tool.

    `command` is the argv prefix, e.g. ``["C:/Program Files/NFIQ2/bin/nfiq2.exe"]``; the
    image path is appended. Its first element must be an absolute path; whether the file
    exists is checked on every call, so an uninstalled tool gives "not computed" rather
    than a failed job. `work_dir` is an existing directory for the temporary image copies.
    """

    def __init__(self, command: Sequence[str], timeout_s: float = DEFAULT_TIMEOUT_S, *, work_dir: Path) -> None:
        self._argv = _check_command(command)
        self._timeout = _check_timeout(timeout_s)
        if not Path(work_dir).is_dir():
            raise ParameterError("work_dir must be an existing directory")
        self._work_dir = Path(work_dir)
        self._version: str | None = None
        self._version_known = False

    @property
    def command(self) -> tuple[str, ...]:
        """The configured argv prefix."""
        return self._argv

    def score(self, png_bytes: bytes) -> Nfiq2Result:
        """Score PNG bytes (500 ppi grayscale export); raise QualityToolError if no score."""
        data = _check_png(png_bytes)
        self._require_tool()
        with tempfile.TemporaryDirectory(prefix="ridge-nfiq2-", dir=self._work_dir) as private:
            image = Path(private) / "export.png"
            _write_private(image, data)
            exit_code, stdout = self._run([*self._argv, str(image)])
        if exit_code != 0:
            raise QualityToolError(f"NFIQ 2 exited with code {exit_code}")
        return Nfiq2Result(score=parse_score(stdout), version=self.version(), raw_exit_code=exit_code)

    def assess(self, png_bytes: bytes) -> Nfiq2Result | Nfiq2NotComputed:
        """Like `score`, but return Nfiq2NotComputed (with the reason) instead of raising."""
        try:
            return self.score(png_bytes)
        except QualityToolError as exc:
            return Nfiq2NotComputed(reason=str(exc))

    def version(self) -> str | None:
        """Best effort: first line printed by ``<command> --version``; None when unknown.

        Asked once per instance. None only means "not reported": it never fails a job.
        """
        if not self._version_known:
            self._version = self._query_version()
            self._version_known = True
        return self._version

    def _query_version(self) -> str | None:
        try:
            self._require_tool()
            exit_code, stdout = self._run([*self._argv, *VERSION_ARGS])
        except QualityToolError:
            return None
        return _version_line(stdout) if exit_code == 0 else None

    def _require_tool(self) -> None:
        if not Path(self._argv[0]).is_file():
            raise QualityToolError("NFIQ 2 is not installed at the configured path")

    def _run(self, argv: list[str]) -> tuple[int, bytes]:
        """Run the tool once with a timeout; return (exit code, stdout of at most MAX_OUTPUT_BYTES)."""
        try:
            done = subprocess.run(  # noqa: S603  # argv list, absolute executable, no shell  # nosec B603
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=self._timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise QualityToolError(f"NFIQ 2 did not finish within {self._timeout:g} s") from exc
        except OSError as exc:
            raise QualityToolError(f"NFIQ 2 could not be started ({type(exc).__name__})") from exc
        if len(done.stdout) > MAX_OUTPUT_BYTES:
            raise QualityToolError(f"NFIQ 2 printed more than {MAX_OUTPUT_BYTES // 1024} KiB")
        return done.returncode, done.stdout
