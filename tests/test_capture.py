"""The capture check (FR-54): findings on synthetic photographs, the record, the text and refused input."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import cv2
import numpy as np
import pytest

from ridge.arrays import ImageU8
from ridge.capture import MIN_CLARITY, NOTICE, SCHEMA, CaptureCheck, check_bytes, check_file, check_text
from ridge.errors import InputError
from ridge.image_io import encode_image
from tests.synthetic import BACKGROUND_BGR, finger_photo, whorl_pattern


def png(img: ImageU8) -> bytes:
    return encode_image(img, ".png")


def jpeg(img: ImageU8, quality: int) -> bytes:
    ok, data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    assert ok
    return data.tobytes()


def ids(check: CaptureCheck, level: str) -> set[str]:
    return {f.id for f in check.findings if f.level == level}


@pytest.fixture(scope="module")
def sharp() -> ImageU8:
    return finger_photo(whorl_pattern(480, 360, 9.0))


def test_a_sharp_located_finger_gives_no_reason_to_retake(sharp: ImageU8) -> None:
    check = check_bytes(png(sharp))
    assert check.verdict == "ok"
    assert check.finger_located
    assert check.finger_share == pytest.approx(0.40, abs=0.02)
    assert check.ridge_spacing_px == pytest.approx(9.0, rel=0.08)
    assert check.clarity is not None
    assert check.clarity > MIN_CLARITY
    assert check.glare_share == 0.0
    assert ids(check, "ok") == {"located", "spacing", "clarity", "no-glare"}
    assert ids(check, "retake") == set()
    assert {"copy", "no-camera-data", "scale"} <= ids(check, "note")  # a PNG is not a camera's original
    assert check.sha256 == hashlib.sha256(png(sharp)).hexdigest()
    assert (check.width, check.height) == (360, 480)


def test_blur_glare_distance_and_a_coarse_photo_ask_for_a_retake(sharp: ImageU8) -> None:
    blurred = check_bytes(png(finger_photo(whorl_pattern(480, 360, 9.0), blur_sigma=5.0)))
    assert blurred.verdict == "retake"
    assert "unclear" in ids(blurred, "retake")
    glared = sharp.copy()
    cv2.circle(glared, (180, 240), 40, (255, 255, 255), -1)
    glare = check_bytes(png(glared))
    assert "glare" in ids(glare, "retake")
    assert glare.glare_share is not None
    assert glare.glare_share > 0.05
    big = np.empty((1440, 1080, 3), np.uint8)
    big[:] = np.asarray(BACKGROUND_BGR, dtype=np.uint8)
    big[480:960, 360:720] = sharp
    small = check_bytes(png(cast(ImageU8, big)))
    assert "small" in ids(small, "retake")
    assert small.finger_share < 0.10
    coarse = check_bytes(png(finger_photo(whorl_pattern(480, 360, 4.5))))
    assert "coarse" in ids(coarse, "retake")
    assert coarse.ridge_spacing_px is not None
    assert coarse.ridge_spacing_px < 6.0


def test_an_unlocated_finger_and_a_recompressed_jpeg_are_named(sharp: ImageU8) -> None:
    grey = check_bytes(png(finger_photo(whorl_pattern(480, 360, 9.0), colour=False)))
    assert not grey.finger_located
    assert grey.finger_share == 1.0
    assert "not-located" in ids(grey, "retake")
    assert "no-glare" not in ids(grey, "ok")  # glare is judged on a located finger only
    low = check_bytes(jpeg(sharp, 60))
    assert "recompressed" in ids(low, "note")
    assert "copy" not in ids(low, "note")  # a camera-format file without editing marks
    high = check_bytes(jpeg(sharp, 95))
    assert "recompressed" not in ids(high, "note")
    assert "no-camera-data" in ids(high, "note")  # OpenCV writes no EXIF


def test_the_record_the_text_and_the_file_path(sharp: ImageU8, tmp_path: Path) -> None:
    path = tmp_path / "finger.png"
    path.write_bytes(png(sharp))
    before = path.stat().st_mtime_ns
    check = check_file(path)
    assert path.stat().st_mtime_ns == before  # read-only
    record = check.to_json()
    assert record["schema"] == SCHEMA
    assert record["verdict"] == "ok"
    assert record["notice"] == NOTICE
    assert {f["id"] for f in record["findings"]} == {f.id for f in check.findings}
    assert all(set(f) == {"id", "level", "text"} for f in record["findings"])
    lines = check_text(check)
    assert lines[0].startswith(f"capture check {check.sha256[:12]}  360 x 480 px")
    assert lines[1] == "No reason to photograph the finger again was found."
    assert lines[-1] == NOTICE
    assert sum(line.startswith("  [ok]") for line in lines) == 4
    retake = check_text(check_bytes(png(finger_photo(whorl_pattern(480, 360, 9.0), colour=False))))
    assert retake[1] == "Photograph the finger again if you still can:"
    assert any(line.startswith("  [retake] No finger was located") for line in retake)


def test_refused_input_raises(tmp_path: Path) -> None:
    with pytest.raises(InputError):
        check_bytes(b"not an image at all")
    path = tmp_path / "note.txt"
    path.write_bytes(b"text")
    with pytest.raises(InputError):
        check_file(path)
