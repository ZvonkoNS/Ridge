"""Cross-architecture comparison of golden sets (PRD NFR-3, architecture §11, ADR-009).

Results from x86-64 and arm64 legitimately differ (SIMD floating point), so they are not
gated for equality. They must, however, stay inside a documented envelope. The envelope is
the cross-architecture difference measured on 2026-10-17 (Handoff_2) plus a small margin:
a regenerated golden set that drifts further fails ``tests/test_cross_architecture.py``, and
widening the envelope is a requirement change that needs Forensic Quality Manager approval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tests.reference import GOLDEN_DIR

# Envelope (measured 2026-10-17: worst agreement 99.85%, ridge spacing +0.52%, size 2 px).
MIN_AGREEMENT = 0.998  # share of equal output pixels, when the output sizes match
MAX_PERIOD_REL_DIFF = 0.01  # measured ridge spacing
MAX_SIZE_DIFF_PX = 2  # output width and height


@dataclass(frozen=True)
class CaseDelta:
    """How one case differs between two golden sets."""

    name: str
    status: tuple[str, str]
    error_match: bool
    found_finger_match: bool
    period: tuple[float, float] | None
    size: tuple[tuple[int, int], tuple[int, int]] | None  # (height, width) per set
    agreement: float | None  # None when the output sizes differ or the case is an error

    @property
    def period_rel_diff(self) -> float:
        """Relative difference of the measured ridge spacing (0 for error cases)."""
        return 0.0 if self.period is None else abs(self.period[1] - self.period[0]) / self.period[0]

    @property
    def size_diff_px(self) -> int:
        """Largest difference in output width or height, in pixels."""
        if self.size is None:
            return 0
        (ha, wa), (hb, wb) = self.size
        return max(abs(ha - hb), abs(wa - wb))

    def violations(self) -> list[str]:
        """Reasons this case is outside the cross-architecture envelope (empty when inside)."""
        problems = []
        if self.status[0] != self.status[1] or not self.error_match:
            problems.append(f"outcome differs: {self.status}")
        if not self.found_finger_match:
            problems.append("finger detection differs")
        if self.period_rel_diff > MAX_PERIOD_REL_DIFF:
            problems.append(f"ridge spacing differs by {self.period_rel_diff:.2%}")
        if self.size_diff_px > MAX_SIZE_DIFF_PX:
            problems.append(f"output size differs by {self.size_diff_px} px")
        if self.agreement is not None and self.agreement < MIN_AGREEMENT:
            problems.append(f"only {self.agreement:.4%} of output pixels agree")
        return problems


def golden_archs(folder: Path = GOLDEN_DIR) -> list[str]:
    """Architectures that have a committed golden set."""
    return sorted(p.stem.removeprefix("v0-") for p in folder.glob("v0-*.json"))


def compare(arch_a: str, arch_b: str, folder: Path = GOLDEN_DIR) -> list[CaseDelta]:
    """Compare the golden sets of two architectures case by case."""
    meta_a = json.loads((folder / f"v0-{arch_a}.json").read_text(encoding="utf-8"))["cases"]
    meta_b = json.loads((folder / f"v0-{arch_b}.json").read_text(encoding="utf-8"))["cases"]
    deltas = []
    with np.load(folder / f"v0-{arch_a}.npz") as npz_a, np.load(folder / f"v0-{arch_b}.npz") as npz_b:
        for name, a in meta_a.items():
            b = meta_b[name]
            status = (a["status"], b["status"])
            if "ok" not in status or status[0] != status[1]:
                deltas.append(CaseDelta(name, status, a.get("error") == b.get("error"), True, None, None, None))
                continue
            img_a, img_b = npz_a[f"{name}__image"], npz_b[f"{name}__image"]
            same_size = img_a.shape == img_b.shape
            agreement = float(np.mean(img_a == img_b)) if same_size else None
            deltas.append(
                CaseDelta(
                    name=name,
                    status=status,
                    error_match=True,
                    found_finger_match=a["found_finger"] == b["found_finger"],
                    period=(a["period"], b["period"]),
                    size=((img_a.shape[0], img_a.shape[1]), (img_b.shape[0], img_b.shape[1])),
                    agreement=agreement,
                )
            )
    return deltas


def markdown_table(deltas: list[CaseDelta]) -> str:
    """Release-handoff table of a comparison."""
    rows = [
        "| Case | Ridge spacing (px) | Output size (w x h) | Output pixels agreeing | Envelope |",
        "| --- | --- | --- | --- | --- |",
    ]
    for d in deltas:
        spacing = "error (same message)" if d.period is None else f"{d.period[0]:.4f} / {d.period[1]:.4f}"
        size = "-" if d.size is None else f"{d.size[0][1]}x{d.size[0][0]} / {d.size[1][1]}x{d.size[1][0]}"
        agree = "-" if d.agreement is None else f"{d.agreement:.4%}"
        verdict = "inside" if not d.violations() else "OUTSIDE: " + "; ".join(d.violations())
        rows.append(f"| {d.name} | {spacing} | {size} | {agree} | {verdict} |")
    return "\n".join(rows)
