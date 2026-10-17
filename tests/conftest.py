"""Shared fixtures. All image data is synthetic (see tests/synthetic.py)."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import PIL
import pytest

from tests.golden_cases import CASES_BY_NAME
from tests.synthetic import ImageU8

GOLDEN_DIR = Path(__file__).parent / "golden"


@dataclass(frozen=True)
class Golden:
    meta: dict[str, Any]
    arrays: dict[str, ImageU8]
    exact: bool  # same platform and library versions as the golden run: demand bit-identical results


@pytest.fixture(scope="session")
def golden() -> Golden:
    meta = json.loads((GOLDEN_DIR / "v0.json").read_text(encoding="utf-8"))
    with np.load(GOLDEN_DIR / "v0.npz") as npz:
        arrays = {key: npz[key] for key in npz.files}
    env = meta["generated_with"]
    # Bit-identical results are expected only where the goldens were made: same OS and library
    # versions (and, in practice, the same CPU, since OpenCV dispatches SIMD code at runtime).
    # CI runners have other CPUs, so CI sets RIDGE_GOLDEN_MODE=tolerant; "exact" forces exactness.
    mode = os.environ.get("RIDGE_GOLDEN_MODE", "auto")
    exact = mode == "exact" or (
        mode == "auto"
        and env["platform"].split("-")[0] == platform.system()
        and env["numpy"] == np.__version__
        and env["opencv"] == cv2.__version__
        and env["pillow"] == PIL.__version__
    )
    return Golden(meta=meta, arrays=arrays, exact=exact)


def write_png(path: Path, bgr: ImageU8) -> Path:
    ok, buf = cv2.imencode(".png", bgr)
    assert ok
    buf.tofile(str(path))
    return path


@pytest.fixture
def photo_png(tmp_path: Path) -> Path:
    """A small synthetic finger photo saved as PNG."""
    return write_png(tmp_path / "finger.png", CASES_BY_NAME["whorl_default"].photo())
