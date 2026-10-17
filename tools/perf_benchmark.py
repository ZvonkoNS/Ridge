"""NFR-1 baseline: extraction time and peak traced memory on synthetic phone-size photos.

    python tools/perf_benchmark.py            # prints JSON; run on the reference workstation (OQ-11)

Peak memory is what ``tracemalloc`` sees (NumPy arrays, including OpenCV outputs); the process
resident size is somewhat higher. Synthetic photos only: no real biometric data.
"""

from __future__ import annotations

import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from tests.synthetic import finger_photo, whorl_pattern  # noqa: E402

from ridge import extract_fingerprint  # noqa: E402

CASES = {"12MP_period16": (3000, 4000, 16.0), "12MP_period24": (3000, 4000, 24.0), "48MP_period32": (6000, 8000, 32.0)}


def measure(height: int, width: int, period: float, runs: int = 2) -> dict[str, Any]:
    """Time and peak traced memory of `runs` extractions of one synthetic photo."""
    img = finger_photo(whorl_pattern(height, width, period))
    times, peak = [], 0
    for _ in range(runs):
        tracemalloc.start()
        start = time.perf_counter()
        result = extract_fingerprint(img)
        times.append(time.perf_counter() - start)
        peak = max(peak, tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
    return {
        "seconds_min": round(min(times), 2),
        "seconds_max": round(max(times), 2),
        "peak_traced_mib": round(peak / 2**20, 1),
        "period_px": round(result.period, 2),
    }


def main() -> int:
    """Run every case and print the results as JSON."""
    results: dict[str, Any] = {
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "opencv_threads": cv2.getNumThreads(),
    }
    for name, (h, w, period) in CASES.items():
        results[name] = measure(h, w, period)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
