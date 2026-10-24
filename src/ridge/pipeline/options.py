"""Opt-in method variants (PRD section 8.7, ADR-014): all off by default, every one recorded.

The characterised pipeline (FR-1, the goldens) runs unchanged unless the examiner turns a
variant on. Variants are engineering candidates for the validation study: they change output
pixels, so they are labelled unvalidated wherever they appear, and every job report records
which were on (``parameters.options``) and what they did (``measurements``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final, Literal

from ridge.errors import ParameterError

type Channel = Literal["green", "red", "blue", "luma", "auto"]
CHANNELS: Final[tuple[Channel, ...]] = ("green", "red", "blue", "luma", "auto")
_FLAGS: Final = ("specular_mask", "upright", "local_frequency", "rectify")


@dataclass(frozen=True, slots=True)
class MethodOptions:
    """Which variants are on. ``channel`` is the colour plane the ridge signal is taken from.

    ``green`` is the characterised default; ``auto`` picks, among green, red, blue and
    luminance, the plane with the strongest measured ridge signal (deterministic, ties in that
    order). ``specular_mask`` excludes specular highlights from the finger area. ``upright``
    rotates the finger so that its axis is vertical with the tip up before extraction.
    ``local_frequency`` filters each pixel with a Gabor bank tuned to its own measured ridge
    spacing instead of one global spacing. ``rectify`` unrolls the pad's curvature before
    extraction (which rotates the finger upright first, as ``upright`` does).
    """

    channel: Channel = "green"
    specular_mask: bool = False
    upright: bool = False
    local_frequency: bool = False
    rectify: bool = False

    def __post_init__(self) -> None:
        if self.channel not in CHANNELS:
            raise ParameterError(f"channel must be one of {', '.join(CHANNELS)}")
        for name in _FLAGS:
            if not isinstance(getattr(self, name), bool):
                raise ParameterError(f"{name} must be true or false")

    @property
    def any(self) -> bool:
        """True when at least one variant differs from the default."""
        return self != MethodOptions()

    def to_json(self) -> dict[str, Any]:
        """JSON-friendly form (recorded in reports and the custody log)."""
        return asdict(self)

    @classmethod
    def from_json(cls, data: object) -> MethodOptions:
        """Rebuild options from a report or an RPC parameter; None or {} means the defaults."""
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ParameterError("options must be an object")
        unknown = set(data) - {"channel", *_FLAGS}
        if unknown:
            raise ParameterError(f"unknown option(s): {', '.join(sorted(str(k) for k in unknown))}")
        return cls(channel=data.get("channel", "green"), **{name: data.get(name, False) for name in _FLAGS})
