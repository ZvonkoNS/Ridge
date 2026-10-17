"""CLI behaviour: naming, folder mode, messages and exit codes."""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

import numpy as np
import pytest

from ridge.cli import main
from ridge.image_io import load_image
from tests.conftest import write_png
from tests.golden_cases import CASES_BY_NAME

ROOT = Path(__file__).resolve().parents[1]


def test_single_file(photo_png: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    assert main([str(photo_png), "-o", str(out)]) == 0
    result = out / "finger_fingerprint.png"
    assert result.is_file()
    captured = capsys.readouterr()
    assert f"-> {result}" in captured.out
    assert "ridge spacing 8.8px" in captured.out
    assert "not for casework" in captured.err  # PRD FR-27


def test_debug_writes_intermediate_images(photo_png: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main([str(photo_png), "-o", str(out), "--debug"]) == 0
    names = sorted(p.name for p in out.iterdir())
    assert names == [
        "finger_debug_gabor.png",
        "finger_debug_normalized.png",
        "finger_debug_quality.png",
        "finger_debug_region.jpg",
        "finger_fingerprint.png",
    ]


def test_folder_mode_skips_own_outputs(photo_png: Path, tmp_path: Path) -> None:
    folder = tmp_path / "photos"
    folder.mkdir()
    photo_png.rename(folder / photo_png.name)
    (folder / "notes.txt").write_text("not an image", encoding="utf-8")
    for name in ("finger_fingerprint.png", "finger_debug_gabor.png"):  # left there by a v0 run
        write_png(folder / name, CASES_BY_NAME["whorl_default"].photo())
    before = sorted(p.name for p in folder.iterdir())
    assert main([str(folder), "-o", str(tmp_path / "second")]) == 0  # outputs in folder are not inputs
    assert sorted(p.name for p in (tmp_path / "second").iterdir()) == ["finger_fingerprint.png"]
    assert sorted(p.name for p in folder.iterdir()) == before


@pytest.mark.parametrize("where", ["same", "inside"])
def test_outputs_never_go_into_an_input_folder(photo_png: Path, tmp_path: Path, where: str) -> None:
    folder = photo_png.parent
    outdir = folder if where == "same" else folder / "out"
    for inputs in ([str(folder)], [str(photo_png)]):
        if where == "inside" and inputs == [str(photo_png)]:
            continue  # a subfolder next to an input file is fine
        with pytest.raises(SystemExit) as excinfo:
            main([*inputs, "-o", str(outdir)])
        assert excinfo.value.code == 2
    assert sorted(p.name for p in folder.iterdir()) == ["finger.png"]  # nothing written, no folder created


def test_failure_reports_and_continues(photo_png: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    noise = write_png(tmp_path / "noise.png", CASES_BY_NAME["noise_only"].photo())
    code = main([str(noise), str(photo_png), "-o", str(tmp_path / "out")])
    assert code == 1
    captured = capsys.readouterr()
    assert f"{noise}: FAILED - no clear ridge pattern found" in captured.err
    assert (tmp_path / "out" / "finger_fingerprint.png").is_file()


def test_missing_input_warns(photo_png: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.jpg"
    assert main([str(missing), str(photo_png), "-o", str(tmp_path / "out")]) == 0
    assert f"warning: {missing} not found, skipped" in capsys.readouterr().err


def test_no_images_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([str(tmp_path / "missing.jpg"), "-o", str(tmp_path / "out")])
    assert excinfo.value.code == 2


def test_options_reach_the_pipeline(photo_png: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main([str(photo_png), "-o", str(out), "--no-crop", "--flip", "--period", "10", "--min-quality", "0.3"]) == 0
    img = load_image(out / "finger_fingerprint.png")
    assert img.shape[:2] == (480, 360)  # --no-crop keeps the photo frame


def test_non_ascii_paths(tmp_path: Path) -> None:
    folder = tmp_path / "primer_čšž_指纹"
    folder.mkdir()
    photo = write_png(folder / "prst_č.png", CASES_BY_NAME["whorl_default"].photo())
    assert main([str(photo), "-o", str(folder / "izhod")]) == 0
    assert (folder / "izhod" / "prst_č_fingerprint.png").is_file()


def test_python_dash_m(photo_png: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["ridge", str(photo_png), "-o", str(tmp_path / "out")])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ridge", run_name="__main__")
    assert excinfo.value.code == 0


def test_legacy_script_shim(photo_png: Path, tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("fingerprint_extract_shim", ROOT / "fingerprint_extract.py")
    assert spec is not None
    assert spec.loader is not None
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    assert shim.main([str(photo_png), "-o", str(tmp_path / "out")]) == 0

    image, info = shim.extract_fingerprint(CASES_BY_NAME["whorl_default"].photo(), debug=("legacy", tmp_path))
    assert set(info) == {"period", "found_finger"}
    assert image.dtype == np.uint8
    assert (tmp_path / "legacy_debug_region.jpg").is_file()
