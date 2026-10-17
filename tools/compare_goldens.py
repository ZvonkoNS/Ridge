"""Report how the committed golden sets differ between CPU architectures.

    python tools/compare_goldens.py                # x86_64 against every other architecture
    python tools/compare_goldens.py x86_64 arm64

Prints a Markdown table for the release handoff (PRD NFR-3) and exits 1 if any case is
outside the cross-architecture envelope defined in tests/cross_arch.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.cross_arch import compare, golden_archs, markdown_table  # noqa: E402


def main(argv: list[str]) -> int:
    """Print the comparison table(s); return 1 if anything is outside the envelope."""
    pairs = [(argv[0], argv[1])] if len(argv) == 2 else [("x86_64", a) for a in golden_archs() if a != "x86_64"]
    outside = False
    for arch_a, arch_b in pairs:
        deltas = compare(arch_a, arch_b)
        print(f"### {arch_a} vs {arch_b}\n")
        print(markdown_table(deltas) + "\n")
        outside = outside or any(d.violations() for d in deltas)
    return 1 if outside else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
