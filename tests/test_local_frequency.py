"""Opt-in local ridge frequency (ADR-014 variant): the spacing map, the interpolated bank, recorded ranges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from ridge import extract_fingerprint
from ridge.arrays import FloatImage
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import load_report, render_report
from ridge.case.store import open_case
from ridge.pipeline import WORK_PERIOD, MethodOptions
from ridge.pipeline.frequency import BANDS, MAX_RATIO, MIN_RATIO, band_filter, banks, local_period_map
from ridge.pipeline.gabor import ridge_orientation
from ridge.pipeline.quality import periodicity
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.conftest import write_png
from tests.synthetic import FloatArray, arch_pattern, finger_photo


def varying_pattern(height: int, width: int, top: float, bottom: float) -> FloatArray:
    """Horizontal ridges whose spacing runs linearly from `top` to `bottom` pixels down the image."""
    spacing = np.linspace(top, bottom, height, dtype=np.float64)
    phase = 2.0 * np.pi * np.cumsum(1.0 / spacing)
    return cast(FloatArray, np.repeat((0.5 + 0.5 * np.cos(phase))[:, None], width, axis=1).astype(np.float32))


def stripes(height: int, width: int, spacing: float) -> FloatImage:
    """A unit-amplitude horizontal ridge wave at working scale."""
    yy = np.arange(height, dtype=np.float32)[:, None]
    return cast(FloatImage, np.repeat(np.cos(2 * np.pi * yy / spacing), width, axis=1).astype(np.float32))


def test_the_spacing_map_follows_the_ridges() -> None:
    p = WORK_PERIOD
    top, bottom = stripes(160, 192, 0.8 * p), stripes(160, 192, 1.25 * p)
    norm = cast(FloatImage, np.vstack([top, bottom]))
    mask = np.ones_like(norm)
    spacing = local_period_map(norm, mask, p)
    assert spacing.shape == norm.shape
    assert spacing.dtype == np.float32
    assert spacing.min() >= MIN_RATIO * p - 1e-3
    assert spacing.max() <= MAX_RATIO * p + 1e-3
    assert np.median(spacing[:120]) == pytest.approx(0.8 * p, rel=0.08)
    assert np.median(spacing[200:]) == pytest.approx(1.25 * p, rel=0.08)
    even = local_period_map(stripes(200, 200, p), np.ones((200, 200), np.float32), p)
    assert np.allclose(even, p, rtol=0.06)
    tiny = local_period_map(stripes(40, 40, p), np.ones((40, 40), np.float32), p)
    assert np.all(tiny == np.float32(p))  # smaller than a block: the nominal spacing throughout
    outside = local_period_map(stripes(200, 200, 0.8 * p), np.zeros((200, 200), np.float32), p)
    assert np.all(outside == np.float32(p))  # no block inside the finger: nominal
    assert BANDS == (0.70, 0.84, 1.0, 1.19, 1.42, 1.68)


def test_untrusted_blocks_are_filled_from_their_neighbours() -> None:
    p = WORK_PERIOD
    wave = stripes(256, 256, 1.25 * p)
    rng = np.random.default_rng(3)
    wave[96:160, 96:160] = rng.normal(0.0, 1.0, (64, 64)).astype(np.float32)  # a blurry, noisy patch
    spacing = local_period_map(wave, np.ones_like(wave), p)
    assert np.median(spacing[96:160, 96:160]) == pytest.approx(1.25 * p, rel=0.1)  # the neighbours' spacing, not p
    half = np.ones_like(wave)
    half[:, 128:] = 0.0  # only the left half is finger: far into the right half, the nominal spacing
    spacing = local_period_map(stripes(256, 256, 1.25 * p), half, p)
    assert np.median(spacing[:, :96]) == pytest.approx(1.25 * p, rel=0.1)
    assert np.allclose(spacing[:, 232:], p)


def test_the_interpolated_bank_answers_a_wave_at_its_own_spacing() -> None:
    p = WORK_PERIOD
    bank_set = banks(p)
    assert [round(s / p, 2) for _, _, s in bank_set] == list(BANDS)
    for ratio in (0.75, 1.0, 1.3, 1.6):
        wave = stripes(160, 160, ratio * p)
        mask = np.ones_like(wave)
        phi = ridge_orientation(wave, mask, p)
        spacing = np.full_like(wave, np.float32(ratio * p))
        enh, power, bank_power = band_filter(wave, phi, spacing, bank_set)
        core = (slice(40, 120), slice(40, 120))
        assert np.abs(enh[core]).max() > 0.7  # the matching bank passes most of the unit wave
        assert np.all(bank_power[core] > 0)
        assert power[core].max() > 0
        assert np.array_equal(enh, band_filter(wave, phi, spacing, bank_set)[0])  # deterministic
    # periodicity at the local spacing: a 0.75 p wave repeats itself at 0.75 p, not at p
    wave = stripes(160, 160, 0.75 * p)
    phi = ridge_orientation(wave, np.ones_like(wave), p)
    at_local = periodicity(wave, phi, p, np.full_like(wave, np.float32(0.75 * p)))
    at_nominal = periodicity(wave, phi, p)
    assert at_local[40:120, 40:120].mean() > at_nominal[40:120, 40:120].mean()


def test_default_options_are_unchanged_and_the_variant_rates_a_varying_finger_better() -> None:
    photo = finger_photo(varying_pattern(600, 400, 7.0, 15.0))  # spacing 7.8 to 14.2 px inside the finger
    plain = extract_fingerprint(photo, debug=True)
    assert plain.local_period_px is None
    local = extract_fingerprint(photo, options=MethodOptions(local_frequency=True), debug=True)
    assert local.local_period_px is not None
    low, median, high = local.local_period_px
    assert low < median < high
    assert high > 1.3 * low  # the recorded range spans the variation
    assert low <= plain.period <= high
    assert plain.debug is not None
    assert local.debug is not None
    h = min(plain.debug.quality.shape[0], local.debug.quality.shape[0])
    w = min(plain.debug.quality.shape[1], local.debug.quality.shape[1])
    top, bottom = (slice(0, h // 3), slice(0, w)), (slice(2 * h // 3, h), slice(0, w))
    fine_plain, coarse_plain = plain.debug.quality[top].mean(), plain.debug.quality[bottom].mean()
    fine_local, coarse_local = local.debug.quality[top].mean(), local.debug.quality[bottom].mean()
    assert coarse_local > 1.1 * coarse_plain  # the coarse end, far from the global spacing, is rated better
    assert fine_local == pytest.approx(fine_plain, rel=0.05)  # the end near the global spacing: the same
    assert np.count_nonzero(local.image) >= 0.95 * np.count_nonzero(plain.image)  # the print is kept
    again = extract_fingerprint(photo, options=MethodOptions(local_frequency=True))
    assert np.array_equal(again.image, local.image)
    assert again.local_period_px == local.local_period_px
    even = extract_fingerprint(finger_photo(arch_pattern(600, 400, 9.0)), options=MethodOptions(local_frequency=True))
    assert even.local_period_px is not None
    assert even.local_period_px[1] == pytest.approx(even.period, rel=0.1)  # an even print: the global spacing
    assert even.local_period_px[2] < 1.2 * even.local_period_px[0]  # and a narrow range


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_jobs_record_the_spacing_range(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    photo = write_png(tmp_path / "varying.png", finger_photo(varying_pattern(600, 400, 7.0, 15.0)))
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(
            case, evidence.sha256, signer, JobParams(options=MethodOptions(local_frequency=True))
        )
        meas = outcome.report["measurements"]
        assert set(meas["local_period_px"]) == {"min", "median", "max"}
        assert meas["local_period_px"]["min"] < meas["local_period_px"]["max"]
        text = render_report(load_report(case, store, outcome.job_id).report, signer.key_id)
        assert "local frequency (spacing" in text
        plain = run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert plain.report["measurements"]["local_period_px"] is None

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(store.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    job = rpc("job.run", {"evidence": evidence.sha256, "options": {"local_frequency": True}})["result"]
    assert job["measurements"]["local_period_px"]["median"] > 0
    session.close()
