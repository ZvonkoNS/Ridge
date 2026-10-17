"""Shared fixtures. All image data is synthetic (see tests/synthetic.py)."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import PIL
import pytest

from tests.golden_cases import CASES, CASES_BY_NAME
from tests.reference import Arrays, Entry, arch_key, golden_paths, load_reference, run_reference
from tests.synthetic import ImageU8


@dataclass(frozen=True)
class Golden:
    """Expected v0 results: per-case metadata entries plus result arrays."""

    cases: dict[str, Entry]
    arrays: Arrays
    exact: bool  # demand bit-identical results (otherwise the same-architecture tolerances apply)
    source: str  # where the expectations come from, for failure messages


@pytest.fixture(scope="session")
def golden() -> Golden:
    """Stored goldens for this machine's CPU architecture (tests/golden/v0-<arch>.*)."""
    arch = arch_key()
    npz_path, json_path = golden_paths(arch)
    if not json_path.is_file():
        pytest.fail(
            f"no golden results for CPU architecture {arch!r}: run the 'golden' workflow on that "
            "architecture (or `python tools/make_golden.py` on such a machine) and commit the files"
        )
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    with np.load(npz_path) as npz:
        arrays = {key: npz[key] for key in npz.files}
    env = meta["generated_with"]
    # Bit-identical results are expected only where the goldens were made: same OS, architecture
    # and library versions (and, in practice, the same CPU, since OpenCV and NumPy dispatch SIMD
    # code at runtime). CI runners have other CPUs, so CI sets RIDGE_GOLDEN_MODE=tolerant;
    # "exact" forces exactness. Bit-identity with v0 on every machine is checked separately
    # against a live v0 run (tests/test_reference_v0.py).
    mode = os.environ.get("RIDGE_GOLDEN_MODE", "auto")
    exact = mode == "exact" or (
        mode == "auto"
        and env["platform"].split("-")[0] == platform.system()
        and env["machine"] == platform.machine()
        and env["numpy"] == np.__version__
        and env["opencv"] == cv2.__version__
        and env["pillow"] == PIL.__version__
    )
    return Golden(cases=meta["cases"], arrays=arrays, exact=exact, source=json_path.name)


@pytest.fixture(scope="session")
def live_v0(tmp_path_factory: pytest.TempPathFactory) -> Golden:
    """Results of the v0 implementation (from git history) run on this machine, now."""
    workdir = tmp_path_factory.mktemp("v0")
    v0 = load_reference(workdir)
    cases: dict[str, Entry] = {}
    arrays: Arrays = {}
    for case in CASES:
        entry, case_arrays = run_reference(v0, case, workdir)
        cases[case.name] = entry
        arrays.update(case_arrays)
    return Golden(cases=cases, arrays=arrays, exact=True, source="live v0 run")


def write_png(path: Path, bgr: ImageU8) -> Path:
    """Save a BGR image as lossless PNG (test fixtures only)."""
    ok, buf = cv2.imencode(".png", bgr)
    assert ok
    buf.tofile(str(path))
    return path


@pytest.fixture
def photo_png(tmp_path: Path) -> Path:
    """A small synthetic finger photo saved as PNG."""
    return write_png(tmp_path / "finger.png", CASES_BY_NAME["whorl_default"].photo())
