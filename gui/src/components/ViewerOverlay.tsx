// What the image viewer draws over the evidence, in the image's own pixels: a further overlay from
// the caller (the job's print area), the region being chosen or already chosen, the ruler and the
// minutiae marks. Overlays never change pixels.
import type { ReactNode } from "react";

import type { Marks } from "../lib/minutiae";
import type { Point, Rect, Size } from "../lib/viewport";

/** One mark: a circle (ending), a square (bifurcation) or a triangle (other), a tick in its direction when it has one, and its label. */
function MarkShape({
  mark,
  size,
  examiner = false,
}: {
  mark: Marks["items"][number];
  size: number;
  examiner?: boolean;
}) {
  const angle = mark.angle === null ? null : (mark.angle * Math.PI) / 180; // counter-clockwise from +x; image y grows downwards
  return (
    <g className={`ov-mark ov-${mark.kind}${examiner ? " ov-examiner" : ""}`}>
      {mark.kind === "ending" ? (
        <circle cx={mark.x} cy={mark.y} r={size} />
      ) : mark.kind === "bifurcation" ? (
        <rect x={mark.x - size} y={mark.y - size} width={size * 2} height={size * 2} />
      ) : (
        <polygon
          points={`${mark.x},${mark.y - size} ${mark.x + size},${mark.y + size} ${mark.x - size},${mark.y + size}`}
        />
      )}
      {angle === null ? null : (
        <line
          x1={mark.x}
          y1={mark.y}
          x2={mark.x + Math.cos(angle) * size * 2.2}
          y2={mark.y - Math.sin(angle) * size * 2.2}
        />
      )}
      {mark.label ? (
        <text x={mark.x + size * 1.3} y={mark.y - size * 0.6} fontSize={size * 2.2}>
          {mark.label}
        </text>
      ) : null}
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
  /** The examiner's marks (saved and unsaved), drawn over the automatic ones. */
  examiner?: Marks | null | undefined;
}

export function ViewerOverlay({ source, zoom, overlay, region, ruler, marks, examiner }: Props) {
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
      {examiner?.items.map((m, i) => (
        <MarkShape key={`e${i}`} mark={m} size={examiner.size} examiner />
      ))}
      {ruler.map((p, i) => (
        <circle key={i} className="ov-point" cx={p.x} cy={p.y} r={6 / zoom} />
      ))}
    </svg>
  );
}
