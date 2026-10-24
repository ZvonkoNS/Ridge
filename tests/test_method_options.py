"""Opt-in method variants (ADR-014): off by default and bit-identical, recorded when on, validated everywhere."""

from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from ridge import extract_fingerprint
from ridge.case import cli_common
from ridge.case.cli import main
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import load_report, render_report
from ridge.case.reproduce import params_from_report
from ridge.case.store import open_case
from ridge.errors import ExtractionError, NoRidgePatternError, ParameterError
from ridge.pipeline import CHANNELS, MethodOptions
from ridge.pipeline.channel import gray_channel, plane
from ridge.pipeline.mask import SPECULAR_LEVEL, without_specular
from ridge.pipeline.period import estimate_period, ridge_signal_strength
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME
from tests.synthetic import ImageU8, finger_photo, whorl_pattern


def test_options_validate_and_round_trip() -> None:
    assert CHANNELS == ("green", "red", "blue", "luma", "auto")
    assert not MethodOptions().any
    assert MethodOptions(channel="auto").any
    assert MethodOptions(specular_mask=True).to_json() == {
        "channel": "green",
        "specular_mask": True,
        "upright": False,
        "local_frequency": False,
        "rectify": False,
    }
    assert MethodOptions.from_json(None) == MethodOptions()
    assert MethodOptions.from_json({}) == MethodOptions()
    assert MethodOptions.from_json({"channel": "luma"}) == MethodOptions(channel="luma")
    with pytest.raises(ParameterError, match="channel"):
        MethodOptions(channel="cyan")  # type: ignore[arg-type]  # the refusal is the point
    with pytest.raises(ParameterError, match="true or false"):
        MethodOptions(specular_mask="yes")  # type: ignore[arg-type]  # the refusal is the point
    with pytest.raises(ParameterError, match="unknown option"):
        MethodOptions.from_json({"channel": "green", "sharpen": True})
    with pytest.raises(ParameterError, match="object"):
        MethodOptions.from_json(["green"])


def test_default_options_are_the_characterised_pipeline() -> None:
    photo = CASES_BY_NAME["whorl_default"].photo()
    plain, explicit = extract_fingerprint(photo), extract_fingerprint(photo, options=MethodOptions())
    assert np.array_equal(plain.image, explicit.image)
    assert plain.gray is not None
    assert explicit.gray is not None
    assert np.array_equal(plain.gray, explicit.gray)
    assert plain.period == explicit.period
    assert (plain.channel_used, plain.specular_fraction, plain.options) == ("green", None, MethodOptions())
    mask = np.ones(photo.shape[:2], bool)
    assert np.array_equal(plane(photo, "green"), photo[:, :, 1].astype(np.float32) / 255.0)
    assert gray_channel(photo, "green", mask)[1] == "green"
    with pytest.raises(ParameterError, match="MethodOptions"):
        extract_fingerprint(photo, options="auto")  # type: ignore[arg-type]  # the refusal is the point


def blue_only_photo() -> ImageU8:
    """A grey finger photo whose ridges survive only in the blue plane (green and red are flat)."""
    photo = finger_photo(whorl_pattern(480, 360, 9.0), colour=False).copy()
    photo[:, :, 1] = 150
    photo[:, :, 2] = 150
    return photo


def test_auto_picks_the_plane_with_the_ridge_signal() -> None:
    photo = blue_only_photo()
    mask = np.ones(photo.shape[:2], bool)
    assert ridge_signal_strength(plane(photo, "blue"), mask) > ridge_signal_strength(plane(photo, "green"), mask)
    result = extract_fingerprint(photo, options=MethodOptions(channel="auto"))
    assert result.channel_used == "blue"
    assert result.image.any()
    again = extract_fingerprint(photo, options=MethodOptions(channel="auto"))
    assert np.array_equal(again.image, result.image)  # deterministic choice
    chosen = extract_fingerprint(photo, options=MethodOptions(channel="blue"))
    assert np.array_equal(chosen.image, result.image)
    assert chosen.channel_used == "blue"
    with pytest.raises(ExtractionError):
        extract_fingerprint(photo)  # the default green plane is flat here: no ridges, or an absurd spacing
    assert estimate_period(plane(photo, "blue"), mask) == pytest.approx(result.period)
    colour = CASES_BY_NAME["whorl_default"].photo()
    assert extract_fingerprint(colour, options=MethodOptions(channel="luma")).channel_used == "luma"


def with_highlight(photo: ImageU8, radius: int = 18) -> ImageU8:
    marked = photo.copy()
    h, w = marked.shape[:2]
    cv2.circle(marked, (w // 2, h // 2), radius, (255, 255, 255), -1)
    return marked


def test_specular_mask_removes_highlights_from_the_finger_area() -> None:
    photo = with_highlight(CASES_BY_NAME["whorl_default"].photo())
    masked = extract_fingerprint(photo, options=MethodOptions(specular_mask=True))
    assert masked.specular_fraction is not None
    assert 0.0 < masked.specular_fraction < 0.2
    assert masked.image.any()
    plain = extract_fingerprint(photo)
    assert plain.specular_fraction is None
    assert not np.array_equal(plain.image, masked.image) or plain.period != masked.period
    mask = np.ones(photo.shape[:2], bool)
    kept, fraction = without_specular(photo, mask, 9.0)
    glare = photo.max(axis=2) >= SPECULAR_LEVEL
    assert not kept[glare].any()  # every highlight pixel is out
    assert fraction > glare.mean()  # grown by half a ridge spacing
    all_white = np.full_like(photo, 255)
    with pytest.raises(NoRidgePatternError, match="highlights"):
        without_specular(all_white, mask, 9.0)
    clean = CASES_BY_NAME["whorl_default"].photo()
    assert extract_fingerprint(clean, options=MethodOptions(specular_mask=True)).specular_fraction == 0.0


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_jobs_record_the_variants_and_reproduce_them(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    photo = write_png(tmp_path / "glare.png", with_highlight(CASES_BY_NAME["whorl_default"].photo()))
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        params = JobParams(options=MethodOptions(channel="auto", specular_mask=True))
        outcome = run_extraction_job(case, evidence.sha256, signer, params)
        report = outcome.report
        assert report["parameters"]["options"] == {
            "channel": "auto",
            "specular_mask": True,
            "upright": False,
            "local_frequency": False,
            "rectify": False,
        }
        assert report["measurements"]["channel_used"] in ("green", "red", "blue", "luma")
        assert report["measurements"]["specular_fraction"] > 0
        assert params_from_report(report["parameters"]) == params
        older = {k: v for k, v in report["parameters"].items() if k != "options"}
        assert params_from_report(older).options == MethodOptions()
        text = render_report(load_report(case, store, outcome.job_id).report, signer.key_id)
        assert "Variants      channel auto (used:" in text
        assert "specular mask (" in text
        assert "unvalidated" in text
        plain = run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert plain.report["parameters"]["options"] == {
            "channel": "green",
            "specular_mask": False,
            "upright": False,
            "local_frequency": False,
            "rectify": False,
        }
        assert plain.report["measurements"]["channel_used"] == "green"
        assert plain.report["measurements"]["specular_fraction"] is None
        assert "Variants" not in render_report(plain.report, signer.key_id)
        with pytest.raises(ParameterError):
            JobParams(options=MethodOptions.from_json({"channel": "cyan"}))


def test_cli_and_sidecar_take_the_variants(
    case_dir: tuple[Path, MemoryKeyStore],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder, keystore = case_dir
    monkeypatch.setattr(cli_common, "KEYSTORE_FACTORY", lambda: keystore)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": PASSPHRASE)
    with open_case(folder, PASSPHRASE, keystore) as case:
        sha = case.import_evidence(photo_file(tmp_path / "in")).sha256
    assert main(["extract", str(folder), "--evidence", sha, "--channel", "luma", "--specular-mask"]) == 0
    out = capsys.readouterr().out
    assert "Variants      channel luma (used: luma), specular mask (0.0 % of the finger removed)" in out
    with pytest.raises(SystemExit):  # argparse refuses an unknown plane
        main(["extract", str(folder), "--evidence", sha, "--channel", "cyan"])

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(folder.parent.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    job = rpc("job.run", {"evidence": sha, "options": {"channel": "red", "specular_mask": False}})["result"]
    assert job["measurements"]["channel_used"] == "red"
    assert rpc("job.run", {"evidence": sha, "options": {"channel": "cyan"}})["error"]
    assert rpc("job.run", {"evidence": sha, "options": {"sharpen": True}})["error"]
    plain = rpc("job.run", {"evidence": sha})["result"]
    assert plain["measurements"]["channel_used"] == "green"
    session.close()
