"""Characterization cases: inputs and parameters whose v0 results are frozen in tests/golden/.

The golden results were produced by the original single-file implementation (git commit
3441cf8) with ``tools/make_golden.py``, one set per CPU architecture. Any intended change to
extraction results must regenerate them deliberately and be recorded in a handoff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.reference import REFERENCE_COMMIT
from tests.synthetic import ImageU8, make_photo

__all__ = ["CASES", "CASES_BY_NAME", "REFERENCE_COMMIT", "Case"]


@dataclass(frozen=True)
class Case:
    name: str
    pattern: str
    height: int
    width: int
    period: float
    colour: bool = True
    params: dict[str, Any] = field(default_factory=dict)
    debug: bool = False

    def photo(self) -> ImageU8:
        return make_photo(self.pattern, self.height, self.width, self.period, colour=self.colour)


CASES: tuple[Case, ...] = (
    Case("whorl_default", "whorl", 480, 360, 9.0, debug=True),
    Case("whorl_flip", "whorl", 480, 360, 9.0, params={"flip": True}),
    Case("whorl_no_crop", "whorl", 480, 360, 9.0, params={"crop": False}),
    Case("whorl_period_override", "whorl", 480, 360, 9.0, params={"period": 10.0}),
    Case("whorl_strict_quality", "whorl", 480, 360, 9.0, params={"min_quality": 0.45}),
    Case("arch_default", "arch", 520, 400, 11.0),
    Case("arch_large_period", "arch", 640, 480, 16.0),
    Case("grey_whole_frame", "whorl", 400, 320, 8.0, colour=False),
    Case("too_low_resolution", "whorl", 480, 360, 9.0, params={"period": 2.5}),
    Case("noise_only", "noise", 480, 360, 9.0),
)

CASES_BY_NAME = {case.name: case for case in CASES}
