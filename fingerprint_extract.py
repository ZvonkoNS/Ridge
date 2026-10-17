#!/usr/bin/env python3
"""Backward-compatible entry point for Ridge v0.

    python fingerprint_extract.py photo.jpg
    python fingerprint_extract.py photos/ -o prints/ --debug

The implementation lives in the ``ridge`` package (``src/ridge``); prefer ``ridge`` or
``python -m ridge`` once the package is installed. ``extract_fingerprint`` keeps the v0
signature: ``(bgr, period=None, min_quality=0.25, flip=False, crop=True, debug=None)``
returning ``(image, {"period": ..., "found_finger": ...})``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running from a source checkout without installing: make ``src/ridge`` importable.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ridge.cli import main  # noqa: E402
from ridge.legacy import extract_fingerprint  # noqa: E402

__all__ = ["extract_fingerprint", "main"]

if __name__ == "__main__":
    sys.exit(main())
