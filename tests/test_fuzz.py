"""Property-based fuzzing of trust boundaries: image decoding and custody-log parsing.

Hostile bytes must only ever produce Ridge's typed errors (or a valid image), never another
exception type, a crash or unbounded resource use (ASVS V5 file handling; CWE-20/400/754).
"""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from ridge.case.crypto import random_key, seal
from ridge.case.custody import CustodyLog
from ridge.errors import DecodeError, InputRejectedError, IntegrityError
from ridge.image_io import ReadLimits, decode_image

FUZZ = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
LIMITS = ReadLimits(max_bytes=4 * 1024 * 1024, max_pixels=4_000_000)
NL = bytes([10])  # line separator of the custody log


def _sample(fmt: str) -> bytes:
    buf = io.BytesIO()
    rng = np.random.default_rng(1)
    Image.fromarray(rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)).save(buf, format=fmt)
    return buf.getvalue()


SAMPLES = {fmt: _sample(fmt) for fmt in ("PNG", "JPEG", "TIFF", "BMP", "WEBP")}


def _decode_or_typed_error(data: bytes) -> None:
    try:
        img = decode_image(data, LIMITS)
    except (InputRejectedError, DecodeError):
        return
    assert img.dtype == np.uint8
    assert img.ndim == 3
    assert img.shape[2] == 3


@FUZZ
@given(st.binary(max_size=4096))
def test_random_bytes_only_raise_typed_errors(data: bytes) -> None:
    _decode_or_typed_error(data)


@FUZZ
@given(
    fmt=st.sampled_from(sorted(SAMPLES)),
    edits=st.lists(st.tuples(st.integers(min_value=0, max_value=10_000), st.integers(0, 255)), min_size=1, max_size=8),
    cut=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000)),
)
def test_mutated_images_only_raise_typed_errors(fmt: str, edits: list[tuple[int, int]], cut: int | None) -> None:
    data = bytearray(SAMPLES[fmt])
    for pos, value in edits:
        data[pos % len(data)] = value
    if cut is not None:
        data = data[: cut % len(data)]
    _decode_or_typed_error(bytes(data))


@FUZZ
@given(lines=st.lists(st.binary(max_size=200), min_size=1, max_size=5), encode=st.booleans())
def test_custody_log_rejects_undecryptable_lines(lines: list[bytes], encode: bool) -> None:
    """Malformed base64 and lines that fail authentication."""
    with tempfile.TemporaryDirectory() as tmp:  # hypothesis re-runs the body: fresh folder per example
        path = Path(tmp) / "custody.jsonl.enc"
        raw = [base64.b64encode(line) if encode else line.replace(NL, b"") for line in lines]
        path.write_bytes(NL.join(raw) + NL)
        with pytest.raises(IntegrityError):
            CustodyLog(path, random_key(), "case", "actor").load()


@FUZZ
@given(payload=st.one_of(st.binary(max_size=300), st.text(max_size=100).map(str.encode), st.just(b"[1, 2]")))
def test_custody_log_rejects_authenticated_garbage(payload: bytes) -> None:
    """Payloads sealed with the right key and position reach the parser and are still refused."""
    key = random_key()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "custody.jsonl.enc"
        log = CustodyLog(path, key, "case", "actor")
        path.write_bytes(base64.b64encode(seal(key, payload, log._aad(0))) + NL)
        with pytest.raises(IntegrityError):
            log.load()


def test_decoder_warnings_are_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    """Regression for a fuzzer finding: a malformed TIFF tag made Pillow emit a UserWarning.

    The finding was a PhotometricInterpretation tag with too many entries (byte 62). Pillow 12
    decoded that file with a warning; Pillow 13 refuses it as unidentified, which Ridge reports as
    InputRejectedError. RowsPerStrip with too many entries (byte 98) still decodes with a warning.
    """
    refused = bytearray(SAMPLES["TIFF"])
    refused[62] = 2
    with pytest.raises(InputRejectedError):
        decode_image(bytes(refused), ReadLimits())
    data = bytearray(SAMPLES["TIFF"])
    data[98] = 2  # RowsPerStrip tag with too many entries
    with caplog.at_level(logging.WARNING, logger="ridge.image_io"):
        decode_image(bytes(data), ReadLimits())
    assert any("image decoder warning" in r.getMessage() for r in caplog.records)
