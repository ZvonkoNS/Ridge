"""Regenerate the golden characterization results from the reference (v0) implementation.

The reference is loaded from git history rather than the working tree, so goldens can be
reproduced at any time:

    python tools/make_golden.py               # reference = tests.golden_cases.REFERENCE_COMMIT
    python tools/make_golden.py --ref <commit>

Writes tests/golden/v0.npz (result arrays) and tests/golden/v0.json (metadata). Only run this
when an extraction change is intended, and record the reason in a handoff.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess  # nosec B404 - fixed git invocation on our own repository
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

import cv2
import numpy as np
import PIL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.golden_cases import CASES, REFERENCE_COMMIT  # noqa: E402

GOLDEN_DIR = ROOT / "tests" / "golden"
DEBUG_STEPS = ("normalized", "gabor", "quality")


def load_reference(ref: str, workdir: Path) -> ModuleType:
    """Import fingerprint_extract.py as it was at git revision `ref`."""
    source = subprocess.run(  # nosec B603 B607 - static argument list, no shell
        ["git", "show", f"{ref}:fingerprint_extract.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    path = workdir / "fingerprint_extract_reference.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("fingerprint_extract_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load reference implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_image(path: Path) -> np.ndarray[Any, Any]:
    """Read an image file unchanged (lossless PNG or the v0 JPEG)."""
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    return img


def main() -> int:
    """Run every case through the reference and write the golden files."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", default=REFERENCE_COMMIT)
    args = ap.parse_args()

    arrays: dict[str, np.ndarray[Any, Any]] = {}
    meta: dict[str, Any] = {
        "reference_commit": args.ref,
        "generated_with": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "pillow": PIL.__version__,
        },
        "cases": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        ref = load_reference(args.ref, workdir)
        for case in CASES:
            debug = (case.name, workdir) if case.debug else None
            entry: dict[str, Any]
            try:
                image, info = ref.extract_fingerprint(case.photo(), debug=debug, **case.params)
            except ValueError as exc:
                entry = {"status": "error", "error": str(exc)}
            else:
                arrays[f"{case.name}__image"] = image
                entry = {
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
            meta["cases"][case.name] = entry
            print(f"{case.name}: {entry['status']}", entry.get("error", ""))

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(GOLDEN_DIR / "v0.npz", allow_pickle=False, **arrays)
    (GOLDEN_DIR / "v0.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
