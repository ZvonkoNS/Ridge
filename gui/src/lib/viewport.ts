// Viewer geometry, kept pure for testing. Coordinates are in SOURCE pixels: the full image after
// EXIF orientation, the space of a job's `roi` and `ruler`. `zoom` is screen pixels per source
// pixel; `pan` is where the image's top-left corner sits in the viewer, in screen pixels.

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Size {
  width: number;
  height: number;
}

export const MIN_ZOOM = 0.02;
export const MAX_ZOOM = 16;
/** Zoom steps the +/- controls move between, as screen pixels per source pixel. */
export const ZOOM_STEPS = [0.05, 0.1, 0.125, 0.25, 0.333, 0.5, 0.667, 1, 1.5, 2, 3, 4, 6, 8, 12, 16];

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** The zoom that fits the whole image into the viewer with a small margin. */
export function fitZoom(image: Size, viewer: Size, margin = 16): number {
  if (image.width <= 0 || image.height <= 0 || viewer.width <= 0 || viewer.height <= 0) {
    return 1;
  }
  const w = Math.max(1, viewer.width - 2 * margin);
  const h = Math.max(1, viewer.height - 2 * margin);
  return clampZoom(Math.min(w / image.width, h / image.height));
}

/** Pan that centres the image in the viewer at `zoom`. */
export function centre(image: Size, viewer: Size, zoom: number): Point {
  return { x: (viewer.width - image.width * zoom) / 2, y: (viewer.height - image.height * zoom) / 2 };
}

export function nextStep(zoom: number, direction: 1 | -1): number {
  if (direction > 0) {
    return ZOOM_STEPS.find((s) => s > zoom * 1.001) ?? MAX_ZOOM;
  }
  return [...ZOOM_STEPS].reverse().find((s) => s < zoom * 0.999) ?? MIN_ZOOM;
}

/** Zoom to `next` keeping the source point under `anchor` (viewer coordinates) in place. */
export function zoomAround(pan: Point, zoom: number, next: number, anchor: Point): Point {
  const sx = (anchor.x - pan.x) / zoom;
  const sy = (anchor.y - pan.y) / zoom;
  return { x: anchor.x - sx * next, y: anchor.y - sy * next };
}

/** Viewer coordinates -> source pixel coordinates (not clamped). */
export function toSource(viewerPoint: Point, pan: Point, zoom: number): Point {
  return { x: (viewerPoint.x - pan.x) / zoom, y: (viewerPoint.y - pan.y) / zoom };
}

/** A source point clamped into the image and rounded to whole pixels. */
export function clampPoint(p: Point, image: Size): Point {
  return {
    x: Math.round(Math.min(image.width, Math.max(0, p.x))),
    y: Math.round(Math.min(image.height, Math.max(0, p.y))),
  };
}

/** The rectangle spanned by two source points, clamped to the image, in whole pixels. */
export function spanRect(a: Point, b: Point, image: Size): Rect {
  const p = clampPoint(a, image);
  const q = clampPoint(b, image);
  return {
    x: Math.min(p.x, q.x),
    y: Math.min(p.y, q.y),
    width: Math.abs(p.x - q.x),
    height: Math.abs(p.y - q.y),
  };
}

/** The part of the image visible in the viewer, in source pixels, at most `maxSide` per side. */
export function visibleRect(
  image: Size,
  viewer: Size,
  pan: Point,
  zoom: number,
  maxSide: number,
): Rect | null {
  const x0 = Math.max(0, Math.floor(-pan.x / zoom));
  const y0 = Math.max(0, Math.floor(-pan.y / zoom));
  const x1 = Math.min(image.width, Math.ceil((viewer.width - pan.x) / zoom));
  const y1 = Math.min(image.height, Math.ceil((viewer.height - pan.y) / zoom));
  if (x1 <= x0 || y1 <= y0) {
    return null;
  }
  const width = Math.min(maxSide, x1 - x0);
  const height = Math.min(maxSide, y1 - y0);
  const cx = Math.floor((x0 + x1) / 2);
  const cy = Math.floor((y0 + y1) / 2);
  const x = Math.max(0, Math.min(image.width - width, cx - Math.floor(width / 2)));
  const y = Math.max(0, Math.min(image.height - height, cy - Math.floor(height / 2)));
  return { x, y, width, height };
}

/** Distance between two points, in the same unit as the points. */
export function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** "125 %" style zoom readout. */
export function zoomLabel(zoom: number): string {
  const pct = zoom * 100;
  return `${pct >= 10 ? Math.round(pct) : pct.toFixed(1)} %`;
}

/** How a bitmap of `bitmapWidth` pixels is drawn when shown `shownWidth` screen pixels wide. */
export function interpolation(bitmapWidth: number, shownWidth: number): "nearest neighbour" | "smoothed" {
  return shownWidth > bitmapWidth * 1.0001 ? "nearest neighbour" : "smoothed";
}
