// View-only measuring between two points of a shown image. Millimetres are given only where the
// image's scale is known (the comparison export, or the processed print through the same scale),
// always with the scale's method and uncertainty; elsewhere only pixels. Nothing is recorded.
import type { Point } from "../lib/viewport";
import type { ScaleSource } from "./ScaleBar";

const METHOD: Record<string, string> = {
  ruler: "ruler in the photo",
  "ridge-period": "ridge-period estimate",
  manual: "examiner value",
  file: "resolution in the file",
};

/** The scale of the shown image, as the scale bar uses it. */
export type KnownScale = ScaleSource;

/** The distance between two points as text, or null until both are placed. */
export function distanceText(points: Point[], scale: KnownScale | null): string | null {
  const [a, b] = points;
  if (!a || !b) {
    return null;
  }
  const px = Math.hypot(b.x - a.x, b.y - a.y);
  const pixels = `${px.toFixed(1)} px`;
  if (!scale || scale.pxPerMm <= 0) {
    return `${pixels} (no known scale for this image)`;
  }
  const mm = px / scale.pxPerMm;
  const plusMinus = scale.uncertaintyPct === null ? "" : ` ± ${scale.uncertaintyPct.toFixed(1)} %`;
  return `${mm.toFixed(2)} mm${plusMinus} (scale: ${METHOD[scale.method] ?? scale.method}) · ${pixels}`;
}

export function MeasureReadout({ points, scale }: { points: Point[]; scale: KnownScale | null }) {
  const text = distanceText(points, scale);
  return (
    <p className="measure-readout" role="status">
      {text
        ? `Distance: ${text}. View only; nothing is recorded.`
        : `Click ${points.length === 0 ? "two points" : "a second point"} on the image to measure.`}
    </p>
  );
}
