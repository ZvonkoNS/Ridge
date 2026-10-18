import { describe, expect, it } from "vitest";

import {
  centre,
  clampPoint,
  fitZoom,
  interpolation,
  nextStep,
  spanRect,
  toSource,
  visibleRect,
  zoomAround,
  zoomLabel,
} from "../lib/viewport";

const photo = { width: 4000, height: 3000 };
const viewer = { width: 832, height: 632 };

describe("viewport geometry", () => {
  it("fits the whole image with a margin and centres it", () => {
    const z = fitZoom(photo, viewer);
    expect(z).toBeCloseTo(0.2, 5);
    expect(centre(photo, viewer, z)).toEqual({ x: 16, y: 16 });
  });

  it("keeps the point under the cursor in place when zooming", () => {
    const pan = { x: 10, y: 20 };
    const anchor = { x: 300, y: 200 };
    const before = toSource(anchor, pan, 0.5);
    const after = toSource(anchor, zoomAround(pan, 0.5, 2, anchor), 2);
    expect(after.x).toBeCloseTo(before.x, 9);
    expect(after.y).toBeCloseTo(before.y, 9);
  });

  it("steps through zoom levels", () => {
    expect(nextStep(1, 1)).toBe(1.5);
    expect(nextStep(1, -1)).toBe(0.667);
    expect(nextStep(16, 1)).toBe(16);
  });

  it("clamps regions to the image in whole pixels", () => {
    expect(clampPoint({ x: -5.2, y: 3100.7 }, photo)).toEqual({ x: 0, y: 3000 });
    expect(spanRect({ x: 900.4, y: 50 }, { x: 100.6, y: -40 }, photo)).toEqual({
      x: 101,
      y: 0,
      width: 799,
      height: 50,
    });
  });

  it("limits full-resolution requests to the visible part and the maximum side", () => {
    const rect = visibleRect(photo, viewer, { x: -2000, y: -1000 }, 1, 2048);
    expect(rect).toEqual({ x: 2000, y: 1000, width: 832, height: 632 });
    const huge = visibleRect(photo, { width: 5000, height: 5000 }, { x: 0, y: 0 }, 1, 2048);
    expect(huge?.width).toBe(2048);
    expect(visibleRect(photo, viewer, { x: 5000, y: 0 }, 1, 2048)).toBeNull();
  });

  it("states the zoom and the interpolation", () => {
    expect(zoomLabel(2)).toBe("200 %");
    expect(zoomLabel(0.05)).toBe("5.0 %");
    expect(interpolation(1000, 2000)).toBe("nearest neighbour");
    expect(interpolation(1000, 500)).toBe("smoothed");
  });
});
