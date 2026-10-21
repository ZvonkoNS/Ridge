"""Where the print lies in the photo: the output's frame and the kept area's outline (pure, no I/O).

The pipeline works on the finger's bounding box, rescaled so ridges are WORK_PERIOD px apart.
These helpers map that working space back to the pixels of the photo the pipeline was given, so
the examiner can see which part of the photo the print was extracted from. Geometry only: the
output pixels do not depend on it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from ridge.arrays import FloatImage

MAX_OUTLINE_POINTS = 256  # bounds the report; the outline is smooth at the scale of a ridge spacing anyway
MAX_SIMPLIFY_STEPS = 12  # each step doubles the tolerance

type Box = tuple[int, int, int, int]  # x, y, width, height in photo pixels
type Polygon = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PrintLocation:
    """The photo pixels the print image shows (`box`) and the outer edge of each kept area."""

    box: Box
    outline: tuple[Polygon, ...]  # largest area first, at most MAX_OUTLINE_POINTS points in all
    parts: int  # separate kept areas; more than len(outline) only if the smallest did not fit

    def shifted(self, dx: int, dy: int) -> PrintLocation:
        """Return this location in the photo it was cut from at (dx, dy), e.g. by a region of interest."""
        x, y, w, h = self.box
        outline = tuple(tuple((px + dx, py + dy) for px, py in poly) for poly in self.outline)
        return PrintLocation(box=(x + dx, y + dy, w, h), outline=outline, parts=self.parts)

    def to_json(self) -> dict[str, Any]:
        """Report form: `box_px` [x, y, width, height], `outline_px` polygons of [x, y] points."""
        return {
            "box_px": list(self.box),
            "outline_px": [[list(p) for p in poly] for poly in self.outline],
            "parts": self.parts,
        }


def _photo_box(window: Box, scale: float, bounds: Box) -> Box:
    """Photo pixels covered by working window (x0, y0, x1, y1), inside bounds (x0, y0, x1, y1)."""
    wx0, wy0, wx1, wy1 = window
    bx0, by0, bx1, by1 = bounds
    left = max(math.floor(bx0 + wx0 / scale), bx0)
    top = max(math.floor(by0 + wy0 / scale), by0)
    right = min(math.ceil(bx0 + wx1 / scale), bx1)
    bottom = min(math.ceil(by0 + wy1 / scale), by1)
    return left, top, right - left, bottom - top


def _simplified(region: FloatImage, period: float) -> tuple[list[np.ndarray], int]:
    """Outer edges of the kept areas (region > 0.5), largest first, within MAX_OUTLINE_POINTS."""
    found, _ = cv2.findContours((region > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    edges = sorted(found, key=cv2.contourArea, reverse=True)  # stable: ties keep OpenCV's order
    epsilon = 0.25 * period
    polys = [cv2.approxPolyDP(e, epsilon, True) for e in edges]
    for _ in range(MAX_SIMPLIFY_STEPS):
        if sum(len(p) for p in polys) <= MAX_OUTLINE_POINTS:
            break
        epsilon *= 2
        polys = [cv2.approxPolyDP(e, epsilon, True) for e in edges]
    kept, total = [], 0
    for poly in polys:
        if total + len(poly) > MAX_OUTLINE_POINTS:
            break
        kept.append(poly)
        total += len(poly)
    return kept, len(edges)


def locate(
    region: FloatImage, *, window: Box | None, scale: float, bounds: Box, size: tuple[int, int], period: float
) -> PrintLocation:
    """Map the working-space print area back to the photo.

    `region` is the working-space print map, `window` the working-space crop (x0, y0, x1, y1) or
    None when the output is the whole photo, `scale` working pixels per photo pixel, `bounds`
    the finger box (x0, y0, x1, y1) it was cut from, `size` the photo's (width, height) and
    `period` the working ridge spacing.
    """
    width, height = size
    box = (0, 0, width, height) if window is None else _photo_box(window, scale, bounds)
    bx0, by0, bx1, by1 = bounds
    polys, parts = _simplified(region, period)
    outline = tuple(
        tuple(
            (
                min(max(round(bx0 + (wx + 0.5) / scale - 0.5), bx0), bx1 - 1),
                min(max(round(by0 + (wy + 0.5) / scale - 0.5), by0), by1 - 1),
            )
            for wx, wy in poly.reshape(-1, 2).tolist()
        )
        for poly in polys
    )
    return PrintLocation(box=box, outline=outline, parts=parts)
