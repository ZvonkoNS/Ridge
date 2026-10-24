import { describe, expect, it } from "vitest";

import type { PrintArea } from "../ipc/types";
import {
  initialView,
  outputLink,
  outputView,
  photoView,
  toOutputPoint,
  toPhotoPoint,
  type OutputLink,
} from "../lib/link";

const AREA: PrintArea = { box_px: [100, 200, 400, 600], outline_px: [], parts: 1 };
const OUTPUT = { width: 800, height: 1200 };

function must(link: OutputLink | null): OutputLink {
  if (link === null) {
    throw new Error("expected a link");
  }
  return link;
}

describe("linked views", () => {
  it("maps photo pixels to output pixels through the print area, with and without the mirror", () => {
    const plain = must(outputLink(AREA, OUTPUT, false));
    expect(plain.k).toBe(2);
    expect(plain.approximate).toBe(false);
    const p = { x: 150, y: 260 };
    expect(toOutputPoint(p, plain)).toEqual({ x: 100, y: 120 });
    expect(toPhotoPoint({ x: 100, y: 120 }, plain)).toEqual(p);
    const mirrored = must(outputLink(AREA, OUTPUT, true));
    expect(toOutputPoint(p, mirrored)).toEqual({ x: 700, y: 120 });
    expect(toPhotoPoint(toOutputPoint(p, mirrored), mirrored)).toEqual(p);
  });

  it("starts at the area's centre with the output at actual size and converts views both ways", () => {
    const link = must(outputLink(AREA, OUTPUT, true));
    const start = initialView(link);
    expect(start).toEqual({ focus: { x: 300, y: 500 }, zoom: 2 });
    const right = outputView(start, link);
    expect(right).toEqual({ focus: { x: 400, y: 600 }, zoom: 1 });
    expect(photoView(right, link)).toEqual(start);
  });

  it("has no link without an area or an output, and says when the frame was warped", () => {
    expect(outputLink(null, OUTPUT, false)).toBeNull();
    expect(outputLink(AREA, null, false)).toBeNull();
    expect(outputLink({ ...AREA, box_px: [0, 0, 0, 0] }, OUTPUT, false)).toBeNull();
    const frame: [number, number][] = [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
    ];
    expect(must(outputLink({ ...AREA, frame_px: frame }, OUTPUT, false)).approximate).toBe(true);
  });
});
