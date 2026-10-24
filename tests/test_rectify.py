"""Opt-in rectification of the pad's curvature (ADR-014 variant): the width profile, the unrolling, the mapping back."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from ridge import extract_fingerprint
from ridge.arrays import Mask
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import load_report, render_report
from ridge.case.store import open_case
from ridge.errors import WorkAreaTooLargeError
from ridge.pipeline import MethodOptions, rectify
from ridge.pipeline.rectify import (
    MAX_ANGLE_DEG,
    MIN_HALF_WIDTH,
    rectification,
    rectify_mask,
    to_canvas,
    to_source,
    width_profile,
)
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.conftest import write_png
from tests.synthetic import FloatArray, finger_photo

WIDTH, HEIGHT = 400, 600
HALF, LONG = 0.32 * WIDTH, 0.40 * HEIGHT  # the semi-axes of finger_photo's ellipse


def cylinder_pattern(height: int, width: int, period: float) -> FloatArray:
    """Vertical ridges of even spacing wrapped on a cylinder whose radius is the finger's half-width in each row."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    half = 0.32 * width * np.sqrt(np.clip(1.0 - ((yy - height / 2.0) / (0.40 * height)) ** 2, 0.0, None))
    u = np.clip((xx - width / 2.0) / np.maximum(half, 1.0), -1.0, 1.0)
    return cast(FloatArray, (0.5 + 0.5 * np.cos(2.0 * np.pi * half * np.arcsin(u) / period)).astype(np.float32))


def ellipse_mask(height: int, width: int, a: float, b: float) -> Mask:
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    return cast(Mask, ((xx - width / 2.0) / a) ** 2 + ((yy - height / 2.0) / b) ** 2 <= 1.0)


def test_the_width_profile_follows_the_finger() -> None:
    profile = width_profile(ellipse_mask(HEIGHT, WIDTH, HALF, LONG))
    assert profile is not None
    centre, half = profile
    assert centre.shape == half.shape == (HEIGHT,)
    assert np.allclose(centre[60:540], WIDTH / 2.0, atol=1.0)
    assert half[300] == pytest.approx(HALF, rel=0.03)
    assert half[180] == pytest.approx(HALF * math.sqrt(1 - (120 / LONG) ** 2), rel=0.05)
    assert np.all(half >= MIN_HALF_WIDTH)  # rows without a usable width take the nearest one's
    assert width_profile(ellipse_mask(100, 100, 20, 20)) is None  # too few rows
    assert width_profile(np.zeros((200, 200), bool)) is None


def test_unrolling_inverts_exactly_and_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    mask = ellipse_mask(HEIGHT, WIDTH, HALF, LONG)
    r = rectification(mask)
    assert r is not None
    reach = math.radians(MAX_ANGLE_DEG)
    assert r.size[1] == HEIGHT
    assert r.size[0] == pytest.approx(2 * HALF * reach, abs=8)
    assert r.half_width_px == pytest.approx(100, rel=0.05)  # the median half-width over the finger's rows
    points = np.array([[200.0, 300.0], [300.0, 300.0], [110.0, 200.0], [290.0, 450.0]])
    assert np.abs(to_source(to_canvas(points, r), r) - points).max() < 1e-6
    w, c = r.half_width[300], r.centre[300]
    at_60_deg = to_canvas(np.array([[c + w * math.sin(math.pi / 3), 300.0]]), r)
    assert at_60_deg[0, 0] - r.middle == pytest.approx(w * math.pi / 3, abs=1e-6)  # arc length, not offset
    beyond = to_canvas(np.array([[c + 0.999 * w, 300.0]]), r)
    assert beyond[0, 0] - r.middle == pytest.approx(w * reach, abs=1e-6)  # clamped at the unroll limit
    unrolled = rectify_mask(mask, r)
    assert unrolled.shape == (HEIGHT, r.size[0])
    assert unrolled[300].sum() == pytest.approx(2 * HALF * reach, abs=4)
    assert not unrolled[:50].any()
    monkeypatch.setattr(rectify, "MAX_RECTIFIED_PIXELS", 10_000)
    with pytest.raises(WorkAreaTooLargeError):
        rectification(mask)


def side_quality(quality: np.ndarray) -> float:
    w = quality.shape[1]
    return float(quality[:, : w // 3].mean() + quality[:, 2 * w // 3 :].mean()) / 2


def test_default_options_are_unchanged_and_the_variant_evens_out_a_curved_pad() -> None:
    photo = finger_photo(cylinder_pattern(HEIGHT, WIDTH, 9.0))
    plain = extract_fingerprint(photo, debug=True)
    assert plain.rectified_half_width_px is None
    assert plain.location is not None
    assert plain.location.frame is None
    rect = extract_fingerprint(photo, options=MethodOptions(rectify=True), debug=True)
    assert rect.rectified_half_width_px == pytest.approx(100, rel=0.08)
    assert rect.rotation_deg is not None
    assert abs(rect.rotation_deg) < 1.0  # already upright: the implied rotation is tiny
    assert rect.period == pytest.approx(9.0, rel=0.05)  # the unrolled spacing is the pattern's
    assert rect.period > plain.period  # the default reads the compressed sides
    assert plain.debug is not None
    assert rect.debug is not None
    assert side_quality(rect.debug.quality) > 1.5 * side_quality(plain.debug.quality)
    assert np.count_nonzero(rect.image) > 1.1 * np.count_nonzero(plain.image)
    location = rect.location
    assert location is not None
    assert location.frame is not None
    assert len(location.frame) > 4  # curved sides
    assert all(0 <= px <= WIDTH and 0 <= py <= HEIGHT for px, py in location.frame)
    assert all(0 <= px < WIDTH and 0 <= py < HEIGHT for poly in location.outline for px, py in poly)
    x, y, w, h = location.box
    assert 0 <= x < x + w <= WIDTH
    assert 0 <= y < y + h <= HEIGHT
    again = extract_fingerprint(photo, options=MethodOptions(rectify=True))
    assert np.array_equal(again.image, rect.image)
    assert again.location == location
    both = extract_fingerprint(photo, options=MethodOptions(rectify=True, local_frequency=True))
    local = extract_fingerprint(photo, options=MethodOptions(local_frequency=True))
    assert both.local_period_px is not None
    assert local.local_period_px is not None
    assert both.local_period_px[2] / both.local_period_px[0] < 1.1  # even after unrolling ...
    assert local.local_period_px[2] / local.local_period_px[0] > 1.1  # ... compressed towards the sides without


def test_an_unlocated_finger_is_left_alone() -> None:
    grey = finger_photo(cylinder_pattern(HEIGHT, WIDTH, 9.0), colour=False)  # no skin colour: not located
    result = extract_fingerprint(grey, options=MethodOptions(rectify=True))
    assert not result.found_finger
    assert result.rectified_half_width_px is None
    assert result.rotation_deg is None
    assert result.location is not None
    assert result.location.frame is None


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_jobs_record_the_rectification(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    photo = write_png(tmp_path / "curved.png", finger_photo(cylinder_pattern(HEIGHT, WIDTH, 9.0)))
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams(options=MethodOptions(rectify=True)))
        meas = outcome.report["measurements"]
        assert meas["rectification"]["max_angle_deg"] == MAX_ANGLE_DEG
        assert meas["rectification"]["half_width_px"] == pytest.approx(100, rel=0.08)
        assert len(meas["print_area"]["frame_px"]) > 4
        text = render_report(load_report(case, store, outcome.job_id).report, signer.key_id)
        assert "rectified (pad half-width" in text
        assert "the scale holds on the centre line" in text
        plain = run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert plain.report["measurements"]["rectification"] is None

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(store.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    job = rpc("job.run", {"evidence": evidence.sha256, "options": {"rectify": True}})["result"]
    assert job["measurements"]["rectification"]["half_width_px"] > 0
    refused = rpc("job.run", {"evidence": evidence.sha256, "options": {"rectify": "yes"}})["error"]
    assert refused["code"] == -32000  # a RidgeError: refused with a message safe to show
    assert "rectify must be true or false" in refused["message"]
    session.close()
