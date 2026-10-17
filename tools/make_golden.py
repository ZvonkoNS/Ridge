"""Regenerate the golden characterization results for this machine's CPU architecture.

The reference (v0) implementation is loaded from git history rather than the working tree,
so goldens can be reproduced at any time:

    python tools/make_golden.py                       # -> tests/golden/v0-<arch>.{npz,json}
    python tools/make_golden.py --out-dir build/golden

Golden files are per architecture family (x86_64, arm64); arm64 goldens are produced on an
Apple silicon runner by the "golden" GitHub Actions workflow. Only regenerate when an
extraction change is intended or a new architecture is added, and record why in a handoff.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import PIL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.golden_cases import CASES  # noqa: E402
from tests.reference import GOLDEN_DIR, REFERENCE_COMMIT, Arrays, arch_key, golden_paths, load_reference, run_reference  # noqa: E402


def main() -> int:
    """Run every case through the reference and write the golden files."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", default=REFERENCE_COMMIT, help="git revision of the reference implementation")
    ap.add_argument("--out-dir", type=Path, default=GOLDEN_DIR, help="output folder (default: tests/golden)")
    args = ap.parse_args()

    arch = arch_key()
    arrays: Arrays = {}
    meta: dict[str, Any] = {
        "reference_commit": args.ref,
        "arch": arch,
        "generated_with": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "pillow": PIL.__version__,
        },
        "cases": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        v0 = load_reference(Path(tmp), args.ref)
        for case in CASES:
            entry, case_arrays = run_reference(v0, case, Path(tmp))
            meta["cases"][case.name] = entry
            arrays.update(case_arrays)
            print(f"{case.name}: {entry['status']}", entry.get("error", ""))

    npz_path, json_path = golden_paths(arch, args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz_path, allow_pickle=False, **arrays)
    json_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {npz_path.name} and {json_path.name} for {arch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
