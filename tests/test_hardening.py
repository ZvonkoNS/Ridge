"""Hardened CLI behaviour and pipeline resource bounds."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

import ridge.cli
from ridge import ImageTooSmallError, ParameterError, WorkAreaTooLargeError, extract_fingerprint
from ridge.cli import main
from ridge.pipeline.period import MAX_MEASURE_PIXELS, estimate_period, measure_scale
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME

# ---------------------------------------------------------------- CLI


def test_existing_outputs_are_not_replaced(photo_png: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    assert main([str(photo_png), "-o", str(out)]) == 0
    first = (out / "finger_fingerprint.png").read_bytes()
    assert main([str(photo_png), "-o", str(out), "--flip"]) == 1
    assert "already exists (use --overwrite to replace it)" in capsys.readouterr().err
    assert (out / "finger_fingerprint.png").read_bytes() == first
    assert main([str(photo_png), "-o", str(out), "--flip", "--overwrite"]) == 0
    assert (out / "finger_fingerprint.png").read_bytes() != first


def test_existing_debug_output_blocks_the_whole_job(photo_png: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "finger_debug_gabor.png").write_bytes(b"earlier result")
    assert main([str(photo_png), "-o", str(out), "--debug"]) == 1
    assert sorted(p.name for p in out.iterdir()) == ["finger_debug_gabor.png"]


def test_skipped_files_are_reported(photo_png: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / "photos"
    folder.mkdir()
    photo_png.rename(folder / "finger.png")
    write_png(folder / "old_fingerprint.png", CASES_BY_NAME["whorl_default"].photo())
    assert main([str(folder), "-o", str(tmp_path / "out")]) == 0
    assert "skipped" in capsys.readouterr().err
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["finger_fingerprint.png"]


def test_symlinks_in_folders_are_not_followed(photo_png: Path, tmp_path: Path) -> None:
    folder = tmp_path / "photos"
    folder.mkdir()
    try:
        (folder / "link.png").symlink_to(photo_png)
    except OSError:
        pytest.skip("creating symlinks needs extra privileges on this system")
    with pytest.raises(SystemExit):  # the only candidate is a link: nothing to process
        main([str(folder), "-o", str(tmp_path / "out")])


def test_disallowed_input_fails_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake = tmp_path / "evidence.jpg"
    fake.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n")
    assert main([str(fake), "-o", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "FAILED - not a supported image" in err
    assert "Traceback" not in err


def test_os_errors_are_reported_without_traceback(
    photo_png: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def denied(path: Path, limits: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(ridge.cli, "load_image", denied)
    assert main([str(photo_png), "-o", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "FAILED - Permission denied" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("verbose", [False, True])
def test_internal_errors_exit_3(
    photo_png: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], verbose: bool
) -> None:
    def bug(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ridge.cli, "extract_fingerprint", bug)
    argv = [str(photo_png), "-o", str(tmp_path / "out")] + (["--verbose"] if verbose else [])
    assert main(argv) == 3
    err = capsys.readouterr().err
    assert "internal error (RuntimeError)" in err
    assert ("Traceback" in err) is verbose


@pytest.mark.parametrize(
    "option",
    [
        ["--min-quality", "1.5"],
        ["--min-quality", "nan"],
        ["--period", "-2"],
        ["--period", "abc"],
        ["--max-megapixels", "0"],
        ["--max-input-mb", "100000"],
    ],
)
def test_out_of_range_options_are_usage_errors(photo_png: Path, tmp_path: Path, option: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([str(photo_png), "-o", str(tmp_path / "out"), *option])
    assert excinfo.value.code == 2


def test_unusable_output_folder_is_a_usage_error(photo_png: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main([str(photo_png), "-o", str(blocker)])
    assert excinfo.value.code == 2


def test_input_limits_reach_the_reader(photo_png: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(photo_png), "-o", str(tmp_path / "out"), "--max-megapixels", "0.1"]) == 1
    assert "the limit is 0 MP" in capsys.readouterr().err


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_output_folder_is_owner_only_on_posix(photo_png: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main([str(photo_png), "-o", str(out)]) == 0
    assert out.stat().st_mode & 0o077 == 0


# ---------------------------------------------------------------- library arguments and resource bounds


@pytest.mark.parametrize(
    ("bgr", "kwargs"),
    [
        (np.zeros((64, 64), np.uint8), {}),
        (np.zeros((64, 64, 3), np.float32), {}),
        (np.zeros((64, 64, 3), np.uint8), {"period": 0.0}),
        (np.zeros((64, 64, 3), np.uint8), {"period": float("inf")}),
        (np.zeros((64, 64, 3), np.uint8), {"min_quality": 1.5}),
    ],
)
def test_invalid_arguments_raise_parameter_error(
    bgr: np.ndarray[tuple[int, ...], np.dtype[np.generic]], kwargs: dict[str, float]
) -> None:
    with pytest.raises(ParameterError):
        extract_fingerprint(bgr, **kwargs)  # type: ignore[arg-type]


def test_huge_work_area_is_refused_before_allocation() -> None:
    flat = np.full((1500, 2000, 3), 128, np.uint8)  # no skin colour: the whole frame is the work area
    with pytest.raises(WorkAreaTooLargeError, match="too large to process"):
        extract_fingerprint(flat, period=3.0)


def test_degenerate_finger_mask_is_refused() -> None:
    gray = np.zeros((300, 300), np.float32)
    mask = np.zeros((300, 300), bool)
    mask[150, 50:250] = True  # a 1 px "finger": v0 tried to upscale the photo 320x here
    with pytest.raises(ImageTooSmallError, match="finger is too small"):
        estimate_period(gray, mask)


def test_measure_scale_is_memory_bounded() -> None:
    assert measure_scale(4000, 3000, 1500.0) == pytest.approx(640 / 1500)  # normal photo: unchanged
    capped = measure_scale(12_000, 10_000, 80.0)  # small finger in a huge frame
    assert capped * capped * 12_000 * 10_000 <= MAX_MEASURE_PIXELS * 1.0001
