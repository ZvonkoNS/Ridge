"""Where the print came from (FR-50 region review): the photo area recorded in the signed job report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ridge.case.identity import create_identity, unlock_identity
from ridge.case.jobs import JobParams, apply_roi, run_extraction_job
from ridge.case.report_html import render_report_html
from ridge.case.reports import SignedReport, render_report
from ridge.case.store import open_case
from ridge.image_io import ReadLimits, decode_image
from ridge.pipeline import extract_fingerprint
from ridge.pipeline.location import MAX_OUTLINE_POINTS, PrintLocation, locate
from tests.case_helpers import FAST_KDF, PASSPHRASE, MemoryKeyStore, new_case, photo_file
from tests.golden_cases import CASES_BY_NAME


@pytest.fixture
def keystore() -> MemoryKeyStore:
    return MemoryKeyStore()


@pytest.fixture
def case_dir(tmp_path: Path, keystore: MemoryKeyStore) -> Path:
    store = tmp_path / "store"
    create_identity(store, PASSPHRASE, keystore, FAST_KDF)
    return new_case(store, keystore)


def run(case_dir: Path, keystore: MemoryKeyStore, photo: Path, params: JobParams) -> Any:
    signer = unlock_identity(case_dir.parent, PASSPHRASE, keystore)
    with open_case(case_dir, PASSPHRASE, keystore) as case:
        evidence = case.import_evidence(photo)
        return run_extraction_job(case, evidence.sha256, signer, params)


@pytest.mark.parametrize("name", ["whorl_default", "arch_default", "arch_large_period", "grey_whole_frame"])
def test_the_box_is_the_photo_area_the_print_image_shows(name: str) -> None:
    case = CASES_BY_NAME[name]
    photo = case.photo()
    result = extract_fingerprint(photo, **case.params)
    assert result.location is not None
    x, y, w, h = result.location.box
    assert min(x, y) >= 0
    assert x + w <= photo.shape[1]
    assert y + h <= photo.shape[0]
    shown_h, shown_w = result.image.shape
    # floor/ceil to whole photo pixels: at most two photo pixels wider than the output frame
    assert 0 <= w * result.output_scale - shown_w <= 2 * result.output_scale + 1
    assert 0 <= h * result.output_scale - shown_h <= 2 * result.output_scale + 1
    points = [p for poly in result.location.outline for p in poly]
    assert 3 <= len(points) <= MAX_OUTLINE_POINTS
    assert result.location.parts == len(result.location.outline) == 1
    assert all(x - 1 <= px <= x + w and y - 1 <= py <= y + h for px, py in points)


def test_the_outline_surrounds_the_kept_ridges() -> None:
    case = CASES_BY_NAME["whorl_default"]
    photo = case.photo()
    result = extract_fingerprint(photo, **case.params, crop=False)  # output in the photo's own pixels
    assert result.location is not None
    assert result.location.box == (0, 0, photo.shape[1], photo.shape[0])
    ys, xs = np.nonzero(result.image)
    outline = np.array(result.location.outline[0])
    margin = 2.0  # rounding to whole pixels and the simplified outline
    assert xs.min() >= outline[:, 0].min() - margin
    assert xs.max() <= outline[:, 0].max() + margin
    assert ys.min() >= outline[:, 1].min() - margin
    assert ys.max() <= outline[:, 1].max() + margin


def test_crop_changes_the_frame_but_not_the_outline() -> None:
    photo = CASES_BY_NAME["whorl_default"].photo()
    cropped, whole = extract_fingerprint(photo), extract_fingerprint(photo, crop=False)
    assert cropped.location is not None
    assert whole.location is not None
    assert cropped.location.outline == whole.location.outline
    assert cropped.location.box != whole.location.box


def test_many_parts_are_capped_and_counted() -> None:
    region = np.zeros((400, 400), np.float32)
    for y in range(5, 400, 20):
        for x in range(5, 400, 20):
            region[y : y + 3, x : x + 3] = 1.0  # 400 separate small areas
    location = locate(region, window=None, scale=1.0, bounds=(0, 0, 400, 400), size=(400, 400), period=12.0)
    assert location.parts == 400
    assert 0 < len(location.outline) < location.parts
    assert sum(len(p) for p in location.outline) <= MAX_OUTLINE_POINTS


def test_shifted_and_json_form() -> None:
    location = PrintLocation(box=(1, 2, 30, 40), outline=(((1, 2), (30, 2), (30, 41)),), parts=1)
    assert location.shifted(10, 20).to_json() == {
        "box_px": [11, 22, 30, 40],
        "outline_px": [[[11, 22], [40, 22], [40, 61]]],
        "parts": 1,
    }


def test_the_report_records_the_area_in_photo_pixels(case_dir: Path, keystore: MemoryKeyStore, tmp_path: Path) -> None:
    path = photo_file(tmp_path / "in", "arch_large_period", "arch.png")
    plain = run(case_dir, keystore, path, JobParams())
    width, height = plain.report["input"]["size_px"]
    whole = run(case_dir, keystore, path, JobParams(roi=(0, 0, width, height)))
    assert whole.report["measurements"]["print_area"] == plain.report["measurements"]["print_area"]

    roi = (width // 8, height // 8, 3 * width // 4, 3 * height // 4)
    part = run(case_dir, keystore, path, JobParams(roi=roi))
    area = part.report["measurements"]["print_area"]
    # the region-of-interest crop's own location, moved to where the crop lies in the photo
    alone = extract_fingerprint(apply_roi(decode_image(path.read_bytes(), ReadLimits()), roi)).location
    assert alone is not None
    assert area == alone.shifted(roi[0], roi[1]).to_json()
    x, y, w, h = area["box_px"]
    assert x >= roi[0]
    assert y >= roi[1]
    assert x + w <= roi[0] + roi[2]
    assert y + h <= roi[1] + roi[3]


def test_readable_reports_state_the_area_and_tolerate_older_reports() -> None:
    area = {"box_px": [70, 54, 222, 372], "outline_px": [[[70, 54], [291, 54], [291, 425]]], "parts": 2}
    report: dict[str, Any] = {"job_id": "j", "measurements": {"ridge_period_px": 9.0, "print_area": area}}
    line = "Print area    x 70, y 54, 222x372 px of the photo (the print image's frame; 2 kept areas)"
    assert line in render_report(report, "k")
    page = render_report_html(SignedReport("j", b"{}", b"", "k", report))
    assert "x 70, y 54, 222x372 px of the photo (the print image&#x27;s frame; 2 kept areas)" in page

    older = {"job_id": "j", "measurements": {"ridge_period_px": 9.0}}  # signed before the area was recorded
    assert "Print area" not in render_report(older, "k")
    assert "Print area" not in render_report_html(SignedReport("j", b"{}", b"", "k", older))
