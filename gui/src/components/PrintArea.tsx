// Where the print came from (FR-50 region review): the last job's print area drawn on the original
// photo. On by default after a job, hidden with one switch. Geometry only, from the job's signed
// report; the outside of the area is dimmed on screen and no pixel of the photo is changed.
import { useState } from "react";

import type { JobResult, PrintArea } from "../ipc/types";
import type { Size } from "../lib/viewport";

export interface AreaOverlay {
  /** Null before a job, or for a report made before Ridge recorded the area. */
  area: PrintArea | null;
  jobId: string | null;
  /** The comparison export is mirrored, so it shows the area the other way round. */
  mirrored: boolean;
  on: boolean;
  setOn: (on: boolean) => void;
}

export function usePrintArea(result: JobResult | null): AreaOverlay {
  const jobId = result?.job_id ?? null;
  // The switch belongs to one job: a new job shows its own area again, even if the last was hidden.
  const [choice, setChoice] = useState<{ jobId: string | null; on: boolean }>({ jobId, on: true });
  const on = choice.jobId === jobId ? choice.on : true;
  const exp = result?.export;
  const mirrored = exp?.produced === true && exp.transforms.some((t) => t.startsWith("mirror:"));
  return {
    area: result?.measurements?.print_area ?? null,
    jobId,
    mirrored,
    on,
    setOn: (next) => {
      setChoice({ jobId, on: next });
    },
  };
}

/** SVG points of an outline; the report gives pixel centres, the viewer's grid has pixel edges. */
function svgPoints(poly: [number, number][]): string[] {
  return poly.map(([x, y]) => `${x + 0.5},${y + 0.5}`);
}

/** The area in the viewer's overlay (image pixels): outside dimmed, edge solid, print frame dashed. */
export function PrintAreaShape({ area, size }: { area: PrintArea; size: Size | null }) {
  const [x, y, width, height] = area.box_px;
  const polys = area.outline_px.filter((p) => p.length >= 2).map(svgPoints);
  const holes = polys.map((p) => `M${p.join("L")}Z`).join("");
  return (
    <g className="ov-area">
      {size ? (
        <path className="ov-area-dim" fillRule="evenodd" d={`M0 0H${size.width}V${size.height}H0Z${holes}`} />
      ) : null}
      <rect className="ov-area-frame" x={x} y={y} width={width} height={height} />
      {polys.map((p, i) => (
        <g key={i}>
          <polygon className="ov-area-halo" points={p.join(" ")} />
          <polygon className="ov-area-edge" points={p.join(" ")} />
        </g>
      ))}
    </g>
  );
}

/** The switch and legend above the original photo; the area in words is in the job summary. */
export function PrintAreaNote({ overlay }: { overlay: AreaOverlay }) {
  if (!overlay.area) {
    return null;
  }
  return (
    <div className="area-note">
      <label className="overlay-toggle overlay-toggle-start">
        <input
          type="checkbox"
          checked={overlay.on}
          onChange={(e) => {
            overlay.setOn(e.target.checked);
          }}
        />
        Show where the print was extracted{overlay.jobId ? ` (job ${overlay.jobId.slice(0, 8)})` : ""}
      </label>
      {overlay.on ? (
        <span className="area-legend">
          Solid line: the area kept as the print. Dashed box: the frame of the print image.
          {overlay.mirrored ? " The comparison export shows this area mirrored." : ""}
        </span>
      ) : null}
    </div>
  );
}

/** One line for the job summary (also what a screen reader gets, since the overlay is drawn only). */
export function areaLine(area: PrintArea | null | undefined): string {
  if (!area) {
    return "not recorded (report made before Ridge recorded it)";
  }
  const [x, y, w, h] = area.box_px;
  const parts = area.parts === 1 ? "" : `; ${area.parts} kept areas`;
  return `x ${x}, y ${y}, ${w} × ${h} px of the photo${parts}`;
}
