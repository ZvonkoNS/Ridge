"""Cross-architecture envelope: committed golden sets must not drift apart (PRD NFR-3).

Runs on every platform against the committed files, so it fails as soon as a regenerated
golden set (any architecture) moves outside the documented envelope in tests/cross_arch.py.
"""

from __future__ import annotations

import pytest

from tests.cross_arch import CaseDelta, compare, golden_archs

REFERENCE_ARCH = "x86_64"


def test_supported_architectures_have_goldens() -> None:
    assert {"x86_64", "arm64"} <= set(golden_archs())


@pytest.mark.parametrize("other", [a for a in golden_archs() if a != REFERENCE_ARCH])
def test_architectures_stay_inside_the_envelope(other: str) -> None:
    deltas = compare(REFERENCE_ARCH, other)
    assert deltas, "no cases compared"
    problems = {d.name: d.violations() for d in deltas if d.violations()}
    assert not problems, f"{REFERENCE_ARCH} vs {other} outside the cross-architecture envelope: {problems}"


def _delta(**overrides: object) -> CaseDelta:
    base: dict[str, object] = {
        "name": "case",
        "status": ("ok", "ok"),
        "error_match": True,
        "found_finger_match": True,
        "period": (10.0, 10.0),
        "size": ((100, 80), (100, 80)),
        "agreement": 1.0,
    }
    base.update(overrides)
    return CaseDelta(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"agreement": 0.997}, "pixels agree"),
        ({"period": (10.0, 10.2)}, "ridge spacing"),
        ({"size": ((100, 80), (100, 83)), "agreement": None}, "output size"),
        ({"found_finger_match": False}, "finger detection"),
        ({"status": ("ok", "error"), "period": None, "size": None, "agreement": None}, "outcome differs"),
        (
            {"status": ("error", "error"), "error_match": False, "period": None, "size": None, "agreement": None},
            "outcome",
        ),
    ],
)
def test_envelope_rejects_drift(overrides: dict[str, object], reason: str) -> None:
    violations = _delta(**overrides).violations()
    assert any(reason in v for v in violations), violations


def test_envelope_accepts_measured_differences() -> None:
    assert _delta(agreement=0.9985, period=(13.7023, 13.7742)).violations() == []
