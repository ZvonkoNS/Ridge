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
from ridge.pipeline.rectify import Rectification, to_source
from ridge.pipeline.upright import Rotation, to_photo

MAX_OUTLINE_POINTS = 256  # bounds the report; the outline is smooth at the scale of a ridge spacing anyway
MAX_SIMPLIFY_STEPS = 12  # each step doubles the tolerance
FRAME_STEPS = 16  # points along each side of the frame when the frame's edges curve (rectified finger)

type Box = tuple[int, int, int, int]  # x, y, width, height in photo pixels
type Polygon = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PrintLocation:
    """The photo pixels the print image shows (`box`) and the outer edge of each kept area."""

    box: Box
    outline: tuple[Polygon, ...]  # largest area first, at most MAX_OUTLINE_POINTS points in all
    parts: int  # separate kept areas; more than len(outline) only if the smallest did not fit
    # When the job rotated the finger upright or unrolled its curvature (ADR-014): the print image's
    # frame as a polygon in photo pixels (`box` is then its axis-aligned bounds) and the rotation
    # applied, in degrees.
    frame: Polygon | None = None
    rotation_deg: float | None = None

    def _corners(self) -> np.ndarray:
        """Return the frame's points, or the box's four corners when the frame is still a rectangle."""
        if self.frame is not None:
            return np.array(self.frame, dtype=np.float64)
        x, y, w, h = self.box
        return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float64)

    def shifted(self, dx: int, dy: int) -> PrintLocation:
        """Return this location in the photo it was cut from at (dx, dy), e.g. by a region of interest."""
        x, y, w, h = self.box
        outline = tuple(tuple((px + dx, py + dy) for px, py in poly) for poly in self.outline)
        frame = None if self.frame is None else tuple((px + dx, py + dy) for px, py in self.frame)
        return PrintLocation((x + dx, y + dy, w, h), outline, self.parts, frame, self.rotation_deg)

    def from_rectified(self, rectification: Rectification) -> PrintLocation:
        """Return this location, computed on the unrolled canvas, in the upright canvas it was unrolled from.

        The frame's vertical edges curve, so the frame becomes a polygon with FRAME_STEPS points per side.
        """
        x, y, w, h = self.box
        steps = np.linspace(0.0, 1.0, FRAME_STEPS + 1)
        left = np.column_stack([np.full_like(steps, x), y + h * steps])
        right = np.column_stack([np.full_like(steps, x + w), y + h * steps[::-1]])
        frame = np.rint(to_source(np.vstack([left, right]), rectification))
        points = tuple((int(px), int(py)) for px, py in frame.tolist())
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        outline = tuple(
            tuple(
                (int(px), int(py))
                for px, py in np.rint(to_source(np.array(poly, dtype=np.float64), rectification)).tolist()
            )
            for poly in self.outline
        )
        return PrintLocation(box, outline, self.parts, points, self.rotation_deg)

    def in_photo(self, rotation: Rotation, size: tuple[int, int]) -> PrintLocation:
        """Return this location, computed on the upright canvas, in the pixels of the photo it was rotated from.

        `size` is the photo's (width, height). Outline points (pixel centres) and the frame's points are
        mapped through the inverse affine, rounded to whole pixels and clipped to the photo.
        """
        width, height = size
        mapped = np.rint(to_photo(self._corners(), rotation))
        frame = tuple((int(min(max(px, 0), width)), int(min(max(py, 0), height))) for px, py in mapped.tolist())
        xs, ys = [p[0] for p in frame], [p[1] for p in frame]
        box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        outline = tuple(
            tuple(
                (int(min(max(px, 0), width - 1)), int(min(max(py, 0), height - 1)))
                for px, py in np.rint(to_photo(np.array(poly, dtype=np.float64), rotation)).tolist()
            )
            for poly in self.outline
        )
        return PrintLocation(box, outline, self.parts, frame, rotation.angle_deg)

    def to_json(self) -> dict[str, Any]:
        """Report form: `box_px` [x, y, width, height], `outline_px` polygons of [x, y] points.

        After an upright rotation or a rectification also `frame_px` (the frame's polygon) and `rotation_deg`.
        """
        area: dict[str, Any] = {
            "box_px": list(self.box),
            "outline_px": [[list(p) for p in poly] for poly in self.outline],
            "parts": self.parts,
        }
        if self.frame is not None:
            area["frame_px"] = [list(p) for p in self.frame]
            area["rotation_deg"] = self.rotation_deg
        return area


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
