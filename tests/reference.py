"""The v0 reference implementation and per-architecture golden files.

v0 (the original single-file script) is loaded straight from git history, so it can be
run next to the package on any machine. That is the strongest evidence that the package
preserves v0 behaviour, independent of platform floating-point differences.

Golden files are stored per CPU architecture family (``tests/golden/v0-<arch>.*``) because
floating-point results legitimately differ between x86-64 and arm64 (PRD NFR-3, R-7).
"""

from __future__ import annotations

import hashlib
import importlib.util
import platform
import shutil
import subprocess  # nosec B404 - fixed git invocation on this repository
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    from tests.golden_cases import Case

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "tests" / "golden"
REFERENCE_COMMIT = "3441cf8d0e9f05fd769315ec906cda6b34f7c6f8"
DEBUG_STEPS = ("normalized", "gabor", "quality")
_ARCH_ALIASES = {"amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}

type Arrays = dict[str, np.ndarray[Any, Any]]
type Entry = dict[str, Any]


def arch_key() -> str:
    """CPU architecture family of this machine: 'x86_64' or 'arm64' (raw name otherwise)."""
    machine = platform.machine().lower()
    return _ARCH_ALIASES.get(machine, machine)


def golden_paths(arch: str, folder: Path = GOLDEN_DIR) -> tuple[Path, Path]:
    """(arrays .npz, metadata .json) of the golden results for `arch`."""
    return folder / f"v0-{arch}.npz", folder / f"v0-{arch}.json"


def load_reference(workdir: Path, ref: str = REFERENCE_COMMIT) -> ModuleType:
    """Import fingerprint_extract.py as it was at git revision `ref`.

    Needs git and the full history (in CI: ``actions/checkout`` with ``fetch-depth: 0``).
    """
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is needed to load the v0 reference implementation")
    source = subprocess.run(  # noqa: S603  # nosec B603 - fixed arguments, no shell
        [git, "show", f"{ref}:fingerprint_extract.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    path = workdir / "fingerprint_extract_v0.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("fingerprint_extract_v0", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the v0 reference implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_image(path: Path) -> np.ndarray[Any, Any]:
    """Read an image file unchanged (lossless PNG or the v0 JPEG)."""
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    return img


def run_reference(v0: ModuleType, case: Case, workdir: Path) -> tuple[Entry, Arrays]:
    """Run one case through v0: (metadata entry, result arrays) in the golden-file layout."""
    arrays: Arrays = {}
    debug = (case.name, workdir) if case.debug else None
    try:
        image, info = v0.extract_fingerprint(case.photo(), debug=debug, **case.params)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, arrays
    arrays[f"{case.name}__image"] = image
    entry: Entry = {
        "status": "ok",
        "shape": list(image.shape),
        "sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "period": info["period"],
        "found_finger": info["found_finger"],
    }
    if case.debug:
        for step in DEBUG_STEPS:
            arrays[f"{case.name}__debug_{step}"] = read_image(workdir / f"{case.name}_debug_{step}.png")
        arrays[f"{case.name}__debug_region"] = read_image(workdir / f"{case.name}_debug_region.jpg")
    return entry, arrays
