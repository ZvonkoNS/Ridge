// What the image viewer draws over the evidence, in the image's own pixels: a further overlay from
// the caller (the job's print area), the region being chosen or already chosen, the ruler and the
// minutiae marks. Overlays never change pixels.
import type { ReactNode } from "react";

import type { Marks } from "../lib/minutiae";
import type { Point, Rect, Size } from "../lib/viewport";

/** One minutia: a circle (ending) or a square (bifurcation) with a tick in its direction. */
function MarkShape({ mark, size }: { mark: Marks["items"][number]; size: number }) {
  const angle = (mark.angle * Math.PI) / 180; // counter-clockwise from +x; image y grows downwards
  const x2 = mark.x + Math.cos(angle) * size * 2.2;
  const y2 = mark.y - Math.sin(angle) * size * 2.2;
  return (
    <g className={`ov-mark ov-${mark.kind}`}>
      {mark.kind === "ending" ? (
        <circle cx={mark.x} cy={mark.y} r={size} />
      ) : (
        <rect x={mark.x - size} y={mark.y - size} width={size * 2} height={size * 2} />
      )}
      <line x1={mark.x} y1={mark.y} x2={x2} y2={y2} />
    </g>
  );
}

interface Props {
  source: Size;
  /** Screen pixels per image pixel: ruler points keep the same size on screen. */
  zoom: number;
  overlay: ReactNode;
  region: Rect | null;
  ruler: Point[];
  marks: Marks | null | undefined;
}

export function ViewerOverlay({ source, zoom, overlay, region, ruler, marks }: Props) {
  const markSize = marks?.size ?? 4;
  return (
    <svg className="viewer-overlay" viewBox={`0 0 ${source.width} ${source.height}`} aria-hidden="true">
      {overlay}
      {region ? (
        <rect className="ov-roi" x={region.x} y={region.y} width={region.width} height={region.height} />
      ) : null}
      {ruler.length === 2 && ruler[0] && ruler[1] ? (
        <line className="ov-ruler" x1={ruler[0].x} y1={ruler[0].y} x2={ruler[1].x} y2={ruler[1].y} />
      ) : null}
      {marks?.items.map((m, i) => (
        <MarkShape key={i} mark={m} size={markSize} />
      ))}
      {ruler.map((p, i) => (
        <circle key={i} className="ov-point" cx={p.x} cy={p.y} r={6 / zoom} />
      ))}
    </svg>
  );
}
