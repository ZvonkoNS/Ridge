"""Minutiae (ridge endings and bifurcations) from an extracted print (PRD FR-40, milestone M3).

Classical method: thin the binary ridge image to a skeleton (Zhang-Suen), classify skeleton
pixels by crossing number (1 = ending, 3 = bifurcation), trace each branch about one ridge
spacing to get the direction, then remove the usual false minutiae with distances scaled to
the ridge spacing: points near the print border, short spurs, broken-ridge ending pairs and
bridge/hole bifurcation pairs.

Conventions (recorded in the JSON template): coordinates are pixels of the print image, origin
top-left; angles in degrees counter-clockwise from +x (image up is +y for angles). An ending
points away from its ridge; a bifurcation points into its fork (mean of the two branches with
the smallest angle between them). ``quality`` (1..100) is a heuristic of distance to the print
border, not an ISO/IEC 29794 measure.

Minutiae support an examiner's comparison. Ridge does not match them against anything and
makes no identification. Accuracy must be validated (PRD §12) before any casework use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, cast

import cv2
import numpy as np

from ridge.arrays import ImageU8, Mask
from ridge.errors import ExtractionError, ParameterError
from ridge.minutiae.skeleton import crossing_number, thin
from ridge.pipeline.imgutil import disk

type Kind = Literal["ending", "bifurcation"]
SCHEMA = "ridge.minutiae/1"
_RING = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))  # clockwise from north
BORDER_MARGIN = 1.0  # in ridge spacings: minutiae closer to the print border are artefacts of the crop
BROKEN_RIDGE = 1.0  # two endings closer than this are one broken ridge
SPUR = 0.8  # an ending this close to a bifurcation is a spur
BRIDGE = 0.6  # two bifurcations this close are a bridge or a hole
MAX_MINUTIAE = 1000  # sanity bound; real prints have well under 200
WORK_PERIOD = 12.0  # ridge spacing the analysis is tuned for
NORMALISE_ABOVE = 2 * WORK_PERIOD  # larger spacings are analysed downscaled


@dataclass(frozen=True)
class Minutia:
    """One minutia in print-image pixels."""

    x: int
    y: int
    kind: Kind
    angle_deg: float
    quality: int


@dataclass(frozen=True)
class MinutiaeResult:
    """Minutiae of one print plus what is needed to interpret them."""

    minutiae: tuple[Minutia, ...]
    width: int
    height: int
    ridge_period_px: float
    space: Literal["print", "export"] = "print"

    def to_json(self) -> dict[str, Any]:
        """Template in Ridge's own documented JSON format (not ISO/IEC 39794-2, see OQ-4)."""
        return {
            "schema": SCHEMA,
            "image": {"width": self.width, "height": self.height, "space": self.space},
            "ridge_period_px": self.ridge_period_px,
            "conventions": {
                "origin": "top-left, pixels",
                "angle": "degrees counter-clockwise from +x; endings point away from the ridge, "
                "bifurcations into the fork",
                "quality": "1-100 heuristic: distance to the print border",
            },
            "minutiae": [
                {"x": m.x, "y": m.y, "type": m.kind, "angle_deg": round(m.angle_deg, 1), "quality": m.quality}
                for m in self.minutiae
            ],
        }


def _branch_starts(skel: Mask, y: int, x: int) -> list[tuple[int, int]]:
    """One start pixel per branch leaving (y, x): runs of skeleton pixels around the 8-ring."""
    h, w = skel.shape
    ring = [(y + dy, x + dx) for dy, dx in _RING]
    on = [0 <= ry < h and 0 <= rx < w and bool(skel[ry, rx]) for ry, rx in ring]
    starts: list[tuple[int, int]] = []
    for i in range(8):
        if on[i] and not on[i - 1]:  # first pixel of a run (the ring is circular)
            run = [i]
            j = (i + 1) % 8
            while on[j] and j != i:
                run.append(j)
                j = (j + 1) % 8
            straight = [k for k in run if k % 2 == 0]  # prefer a 4-neighbour as the branch start
            starts.append(ring[(straight or run)[0]])
    return starts


def _trace(skel: Mask, origin: tuple[int, int], start: tuple[int, int], length: int) -> tuple[int, int]:
    """Follow the skeleton from `start` away from `origin` for up to `length` steps (deterministic)."""
    h, w = skel.shape
    visited = {origin, start}
    prev, (cy, cx) = origin, start
    for _ in range(length - 1):
        nxt = [
            (cy + dy, cx + dx)
            for dy, dx in _RING
            if 0 <= cy + dy < h
            and 0 <= cx + dx < w
            and skel[cy + dy, cx + dx]
            and (cy + dy, cx + dx) not in visited
            and max(abs(cy + dy - prev[0]), abs(cx + dx - prev[1])) > 1  # no corner shortcuts
        ]
        if not nxt:
            break  # end of the ridge
        # Junction clusters leave several candidates: keep moving away from the minutia.
        step = max(nxt, key=lambda p: (p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
        prev, (cy, cx) = (cy, cx), step
        visited.add((cy, cx))
    return cy, cx


def _angle(y0: int, x0: int, y1: int, x1: int) -> float:
    return math.degrees(math.atan2(-(y1 - y0), x1 - x0)) % 360.0


def _direction(skel: Mask, y: int, x: int, kind: Kind, length: int) -> float | None:
    branches = [_angle(y, x, *_trace(skel, (y, x), s, length)) for s in _branch_starts(skel, y, x)]
    if kind == "ending":
        return (branches[0] + 180.0) % 360.0 if len(branches) == 1 else None
    if len(branches) != 3:
        return None
    pairs = [(i, j) for i in range(3) for j in range(i + 1, 3)]

    def gap(p: tuple[int, int]) -> float:
        d = abs(branches[p[0]] - branches[p[1]]) % 360.0
        return min(d, 360.0 - d)

    i, j = min(pairs, key=gap)
    a, b = math.radians(branches[i]), math.radians(branches[j])
    return math.degrees(math.atan2(math.sin(a) + math.sin(b), math.cos(a) + math.cos(b))) % 360.0


def _drop_close_pairs(points: list[Minutia], kinds: tuple[Kind, Kind], limit: float) -> list[Minutia]:
    """Remove both members of every pair of the given kinds closer than `limit`."""
    drop: set[int] = set()
    for i, a in enumerate(points):
        for j in range(i + 1, len(points)):
            b = points[j]
            same_kinds = {a.kind, b.kind} == set(kinds) or kinds[0] == kinds[1] == a.kind == b.kind
            if same_kinds and math.hypot(a.x - b.x, a.y - b.y) < limit:
                drop.update((i, j))
    return [m for k, m in enumerate(points) if k not in drop]


def _check_print(image: object) -> ImageU8:
    if not (isinstance(image, np.ndarray) and image.ndim == 2 and image.dtype == np.uint8):
        raise ParameterError("print_image must be an H x W uint8 image")
    return cast(ImageU8, image)


def extract_minutiae(print_image: ImageU8, ridge_period_px: float) -> MinutiaeResult:
    """Find minutiae in a white-ridges-on-black print (``ExtractionResult.image``).

    `ridge_period_px` is the ridge spacing in the print image's pixels
    (``ExtractionResult.period * ExtractionResult.output_scale``). Prints with a ridge spacing
    above NORMALISE_ABOVE are analysed at ~WORK_PERIOD pixels per ridge and the minutiae are
    mapped back, so any spacing the pipeline accepts works. Raises ExtractionError when the
    print has implausibly many candidates (not a usable ridge image).
    """
    print_image = _check_print(print_image)
    if not (math.isfinite(ridge_period_px) and 3.0 <= ridge_period_px <= 10_000.0):
        raise ParameterError("ridge_period_px must be a finite spacing of at least 3 pixels")
    period = float(ridge_period_px)
    h, w = print_image.shape
    if period <= NORMALISE_ABOVE:
        return MinutiaeResult(tuple(_extract(print_image, period)), w, h, period)
    f = WORK_PERIOD / period
    small = cv2.resize(print_image, (max(1, round(w * f)), max(1, round(h * f))), interpolation=cv2.INTER_AREA)
    found = _extract(cast(ImageU8, np.where(small > 127, 255, 0).astype(np.uint8)), WORK_PERIOD)
    back = tuple(
        Minutia(
            min(w - 1, round((m.x + 0.5) / f - 0.5)),
            min(h - 1, round((m.y + 0.5) / f - 0.5)),
            m.kind,
            m.angle_deg,
            m.quality,
        )
        for m in found
    )
    return MinutiaeResult(back, w, h, period)


def _extract(print_image: ImageU8, period: float) -> list[Minutia]:
    ridges = print_image > 0
    skel = thin(ridges)
    cn = crossing_number(skel)
    region = cv2.morphologyEx(ridges.astype(np.uint8), cv2.MORPH_CLOSE, disk(2 * period))  # fill the valleys
    border = cv2.distanceTransform(np.pad(region, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    length = max(3, round(period))

    found: list[Minutia] = []
    for kind, value in (("ending", 1), ("bifurcation", 3)):
        ys, xs = np.nonzero(cn == value)
        for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
            if border[y, x] <= BORDER_MARGIN * period:
                continue
            angle = _direction(skel, y, x, kind, length)  # type: ignore[arg-type]
            if angle is None:
                continue
            quality = int(np.clip(round(100 * border[y, x] / (3 * period)), 1, 100))
            found.append(Minutia(x, y, kind, angle, quality))  # type: ignore[arg-type]
            if len(found) > MAX_MINUTIAE:
                raise ExtractionError("too many minutiae candidates: the print is not a usable ridge image")

    found = _drop_close_pairs(found, ("ending", "bifurcation"), SPUR * period)
    found = _drop_close_pairs(found, ("ending", "ending"), BROKEN_RIDGE * period)
    found = _drop_close_pairs(found, ("bifurcation", "bifurcation"), BRIDGE * period)
    found.sort(key=lambda m: (m.y, m.x))
    return found


def to_export_space(result: MinutiaeResult, *, factor: float, mirrored: bool) -> MinutiaeResult:
    """Map minutiae into comparison-export pixels (scaled by `factor`, optionally mirrored)."""
    if not (math.isfinite(factor) and factor > 0):
        raise ParameterError("factor must be a positive number")
    moved = tuple(
        Minutia(
            x=round(((result.width - 1 - m.x) if mirrored else m.x) * factor),
            y=round(m.y * factor),
            kind=m.kind,
            angle_deg=((180.0 - m.angle_deg) % 360.0) if mirrored else m.angle_deg,
            quality=m.quality,
        )
        for m in result.minutiae
    )
    return MinutiaeResult(
        moved, round(result.width * factor), round(result.height * factor), result.ridge_period_px * factor, "export"
    )
