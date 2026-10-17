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

from ridge.case.crypto import random_key
from ridge.case.custody import CustodyLog
from ridge.errors import DecodeError, InputRejectedError, IntegrityError
from ridge.image_io import ReadLimits, decode_image

FUZZ = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
LIMITS = ReadLimits(max_bytes=4 * 1024 * 1024, max_pixels=4_000_000)


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
def test_custody_log_rejects_garbage(lines: list[bytes], encode: bool) -> None:
    with tempfile.TemporaryDirectory() as tmp:  # hypothesis re-runs the body: fresh folder per example
        path = Path(tmp) / "custody.jsonl.enc"
        raw = [base64.b64encode(line) if encode else line.replace(b"\n", b"") for line in lines]
        path.write_bytes(b"\n".join(raw) + b"\n")
        log = CustodyLog(path, random_key(), "case", "actor")
        try:
            log.load()
        except IntegrityError:
            return
        raise AssertionError("garbage custody lines were accepted")


def test_decoder_warnings_are_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    """Regression for a fuzzer finding: a malformed TIFF tag made Pillow emit a UserWarning."""
    data = bytearray(SAMPLES["TIFF"])
    data[62] = 2  # PhotometricInterpretation tag with too many entries
    with caplog.at_level(logging.WARNING, logger="ridge.image_io"):
        _decode_or_typed_error(bytes(data))
    assert any("image decoder warning" in r.getMessage() for r in caplog.records)
