// Linking the original photo and a job's output in the review panel (FR-56): the output image covers
// the photo's print area, so a point of one maps to a point of the other through the area's box, the
// output's pixels per photo pixel and, for a comparison export, the mirror. The link is geometry for
// the two viewers only: it records nothing and changes no pixel. After an upright rotation or a
// rectification the frame is no longer a rectangle and the box is only its bounds, so the link is
// approximate and says so.
import type { PrintArea } from "../ipc/types";
import type { Point, Rect, Size } from "./viewport";

export interface OutputLink {
  /** The print area in photo pixels. */
  box: Rect;
  /** Output pixels per photo pixel. */
  k: number;
  /** The output is mirrored left to right (a comparison export). */
  mirrored: boolean;
  /** The output's width in its own pixels. */
  width: number;
  /** The frame was tilted or curved: the box is its bounds, so the mapping is approximate. */
  approximate: boolean;
}

/** A shared view: the photo pixel at the centre of both viewers and the screen pixels per photo pixel. */
export interface LinkedView {
  focus: Point;
  zoom: number;
}

export function outputLink(
  area: PrintArea | null | undefined,
  output: Size | null,
  mirrored: boolean,
): OutputLink | null {
  if (!area || !output) {
    return null;
  }
  const [x, y, width, height] = area.box_px;
  if (width <= 0 || height <= 0 || output.width <= 0) {
    return null;
  }
  return {
    box: { x, y, width, height },
    k: output.width / width,
    mirrored,
    width: output.width,
    approximate: area.frame_px !== undefined,
  };
}

/** A photo pixel as a pixel of the output image. */
export function toOutputPoint(p: Point, link: OutputLink): Point {
  const ox = (p.x - link.box.x) * link.k;
  return { x: link.mirrored ? link.width - ox : ox, y: (p.y - link.box.y) * link.k };
}

/** An output pixel as a pixel of the photo. */
export function toPhotoPoint(p: Point, link: OutputLink): Point {
  const ox = link.mirrored ? link.width - p.x : p.x;
  return { x: link.box.x + ox / link.k, y: link.box.y + p.y / link.k };
}

/** Where linking starts: the print area's centre, with the output at its actual size. */
export function initialView(link: OutputLink): LinkedView {
  return { focus: { x: link.box.x + link.box.width / 2, y: link.box.y + link.box.height / 2 }, zoom: link.k };
}

/** The output viewer's focus and zoom for a shared view. */
export function outputView(view: LinkedView, link: OutputLink): LinkedView {
  return { focus: toOutputPoint(view.focus, link), zoom: view.zoom / link.k };
}

/** The shared view from the output viewer's focus and zoom. */
export function photoView(view: LinkedView, link: OutputLink): LinkedView {
  return { focus: toPhotoPoint(view.focus, link), zoom: view.zoom * link.k };
}
