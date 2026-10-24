"""Opt-in rotation to upright (ADR-014 variant): axis and tip from the mask, location mapped back, recorded."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import pytest

from ridge import extract_fingerprint
from ridge.arrays import Mask
from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, run_extraction_job
from ridge.case.reports import load_report, render_report
from ridge.case.store import open_case
from ridge.pipeline import MethodOptions
from ridge.pipeline.upright import (
    finger_axis,
    rotate_mask,
    rotation_angle,
    to_photo,
    upright_rotation,
)
from ridge.sidecar.handlers import Session
from ridge.sidecar.server import handle
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME
from tests.synthetic import ImageU8, finger_photo, whorl_pattern


def tapered_mask(angle_deg: float = 0.0, *, size: int = 400) -> Mask:
    """A finger-like trapezoid, narrow end (the tip) pointing up, turned by `angle_deg` counter-clockwise on screen."""
    canvas = np.zeros((size, size), np.uint8)
    poly = np.array([[-30, -150], [30, -150], [70, 150], [-70, 150]], np.float64)  # narrow top, wide bottom
    a = math.radians(angle_deg)
    turn = np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])  # OpenCV's screen rotation
    pts = (poly @ turn.T + size / 2).round().astype(np.int32)
    cv2.fillPoly(canvas, [pts], 255)
    return canvas > 0


def axis_up(mask: Mask) -> tuple[float, float]:
    axis = finger_axis(mask)
    assert axis is not None
    return axis[2], axis[3]


def test_axis_and_tip_from_a_tapered_mask() -> None:
    ux, uy = axis_up(tapered_mask())
    assert uy < -0.99  # the narrow end is up
    assert abs(rotation_angle(ux, uy)) < 1.0
    ux, uy = axis_up(tapered_mask()[::-1].copy())  # flipped: the tip points down
    assert uy > 0.99
    assert abs(abs(rotation_angle(ux, uy)) - 180.0) < 1.0
    for turned in (40.0, -75.0, 120.0):
        rotation = upright_rotation(tapered_mask(turned))
        assert rotation is not None
        assert abs(abs(rotation.angle_deg) - abs(turned)) < 2.0 or abs(abs(rotation.angle_deg) - abs(turned)) > 358
        back = rotate_mask(tapered_mask(turned), rotation)
        ux, uy = axis_up(back)
        assert uy < -0.99  # upright after the rotation
        assert abs(ux) < 0.05
        assert back.shape == (rotation.size[1], rotation.size[0])


def test_symmetric_and_degenerate_masks() -> None:
    ellipse = np.zeros((300, 200), np.uint8)
    cv2.ellipse(ellipse, (100, 150), (50, 120), 0, 0, 360, 255, -1)
    rotation = upright_rotation(ellipse > 0)
    assert rotation is not None
    assert abs(rotation.angle_deg) < 0.5  # a vertical ellipse: both ends alike, the smaller turn wins
    wide = np.zeros((200, 300), np.uint8)
    cv2.ellipse(wide, (150, 100), (120, 50), 0, 0, 360, 255, -1)
    sideways = upright_rotation(wide > 0)
    assert sideways is not None
    assert abs(abs(sideways.angle_deg) - 90.0) < 0.5
    assert upright_rotation(np.zeros((50, 50), bool)) is None  # nothing
    disk = np.zeros((200, 200), np.uint8)
    cv2.circle(disk, (100, 100), 60, 255, -1)
    assert upright_rotation(disk > 0) is None or abs(upright_rotation(disk > 0).angle_deg) <= 180  # type: ignore[union-attr]
    small = np.zeros((20, 20), bool)
    small[5:9, 5:9] = True
    assert finger_axis(small) is None  # below MIN_AXIS_PIXELS


def turned_photo(photo: ImageU8, angle: float) -> ImageU8:
    h, w = photo.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float64) @ matrix[:, :2].T + matrix[:, 2]
    low, high = corners.min(axis=0), corners.max(axis=0)
    size = (math.ceil(high[0] - low[0]), math.ceil(high[1] - low[1]))
    matrix[0, 2] -= low[0]
    matrix[1, 2] -= low[1]
    background = tuple(int(v) for v in photo[0, 0])  # keep the plain background colour for the skin mask
    turned = cv2.warpAffine(
        photo, matrix, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=background
    )
    return cast(ImageU8, turned)


def test_pipeline_rotates_a_turned_finger_back_and_maps_the_location_to_the_photo() -> None:
    photo = CASES_BY_NAME["whorl_default"].photo()
    plain = extract_fingerprint(photo)
    turned = turned_photo(photo, 30.0)
    result = extract_fingerprint(turned, options=MethodOptions(upright=True))
    assert result.rotation_deg is not None
    assert abs(result.rotation_deg + 30.0) < 3.0  # turned back by about the same angle
    assert abs(result.image.shape[0] - plain.image.shape[0]) <= 0.1 * plain.image.shape[0] + 4
    assert abs(result.image.shape[1] - plain.image.shape[1]) <= 0.1 * plain.image.shape[1] + 4
    assert result.location is not None
    area = result.location.to_json()
    h, w = turned.shape[:2]
    assert len(area["frame_px"]) == 4
    assert all(0 <= x <= w and 0 <= y <= h for x, y in area["frame_px"])
    assert area["rotation_deg"] == result.rotation_deg
    bx, by, bw, bh = area["box_px"]
    assert bx >= 0
    assert by >= 0
    assert bx + bw <= w
    assert by + bh <= h
    assert all(0 <= x < w and 0 <= y < h for poly in area["outline_px"] for x, y in poly)
    assert bw < w
    assert bh < h
    again = extract_fingerprint(turned, options=MethodOptions(upright=True))
    assert np.array_equal(again.image, result.image)
    assert again.rotation_deg == result.rotation_deg


def test_an_upright_photo_barely_turns_and_an_unlocated_finger_is_left_alone() -> None:
    photo = CASES_BY_NAME["whorl_default"].photo()
    result = extract_fingerprint(photo, options=MethodOptions(upright=True))
    assert result.rotation_deg is not None
    assert abs(result.rotation_deg) < 0.5
    plain = extract_fingerprint(photo)
    assert abs(result.image.shape[0] - plain.image.shape[0]) <= 2
    assert result.location is not None
    assert "frame_px" in result.location.to_json()
    grey = finger_photo(whorl_pattern(400, 320, 8.0), colour=False)  # no skin colour: the finger is not located
    unrotated = extract_fingerprint(grey, options=MethodOptions(upright=True))
    assert unrotated.rotation_deg is None
    assert np.array_equal(unrotated.image, extract_fingerprint(grey).image)
    assert plain.location is not None
    assert "frame_px" not in plain.location.to_json()  # untouched reports keep the plain area record


def test_to_photo_inverts_the_canvas_mapping() -> None:
    mask = tapered_mask(33.0)
    rotation = upright_rotation(mask)
    assert rotation is not None
    points = np.array([[10.0, 20.0], [200.0, 150.0], [399.0, 0.0]])
    on_canvas = points @ rotation.matrix[:, :2].T + rotation.matrix[:, 2]
    assert np.allclose(to_photo(on_canvas, rotation), points, atol=1e-6)


@pytest.fixture
def case_dir(tmp_path: Path) -> tuple[Path, MemoryKeyStore]:
    keystore = MemoryKeyStore()
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore), keystore


def test_jobs_record_the_rotation(case_dir: tuple[Path, MemoryKeyStore], tmp_path: Path) -> None:
    folder, keystore = case_dir
    store = folder.parent
    signer = unlock_identity(store, PASSPHRASE, keystore)
    photo = write_png(tmp_path / "turned.png", turned_photo(CASES_BY_NAME["whorl_default"].photo(), 30.0))
    with open_case(folder, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        outcome = run_extraction_job(case, evidence.sha256, signer, JobParams(options=MethodOptions(upright=True)))
        meas = outcome.report["measurements"]
        assert outcome.report["parameters"]["options"]["upright"] is True
        assert abs(meas["upright_rotation_deg"] + 30.0) < 3.0
        assert "frame_px" in meas["print_area"]
        text = render_report(load_report(case, store, outcome.job_id).report, signer.key_id)
        assert "upright (rotated -" in text
        plain = run_extraction_job(case, evidence.sha256, signer, JobParams())
        assert plain.report["measurements"]["upright_rotation_deg"] is None

    session = Session(keystore_factory=lambda: keystore)

    def rpc(method: str, params: dict[str, Any]) -> Any:
        message = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return json.loads(handle(json.dumps(message).encode(), session))

    rpc("session.unlock", {"store": str(store.resolve()), "case_id": folder.name, "passphrase": PASSPHRASE})
    job = rpc("job.run", {"evidence": evidence.sha256, "options": {"upright": True}})["result"]
    assert abs(job["measurements"]["upright_rotation_deg"] + 30.0) < 3.0
    assert rpc("job.run", {"evidence": evidence.sha256, "options": {"upright": "yes"}})["error"]
    session.close()
