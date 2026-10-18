// Extraction parameters. Every value sent with a job is visible here and recorded in the signed
// report; the region and the ruler can be drawn on the photo or typed (no dragging required,
// WCAG 2.2 SC 2.5.7).
import type { ChangeEvent, ReactNode } from "react";

import type { JobOptions } from "../ipc/types";
import { distance, type Point, type Rect, type Size } from "../lib/viewport";

export interface Params {
  period: string;
  minQuality: number;
  flip: boolean;
  crop: boolean;
  debug: boolean;
  export: boolean;
  mirror: boolean;
  ppi: number;
  minutiae: boolean;
  roi: Rect | null;
  ruler: Point[];
  rulerMm: string;
}

export const DEFAULT_PARAMS: Params = {
  period: "",
  minQuality: 0.25,
  flip: false,
  crop: true,
  debug: false,
  export: true,
  mirror: true,
  ppi: 500,
  minutiae: false,
  roi: null,
  ruler: [],
  rulerMm: "10",
};

/** Turn the form into job options, or explain what to fix. */
export function toOptions(evidence: string, p: Params, photo?: Size | null): JobOptions | string {
  const period = p.period.trim() === "" ? null : Number(p.period);
  if (period !== null && !(period >= 2 && period <= 200)) {
    return "Ridge period must be empty (measure automatically) or 2 to 200 pixels.";
  }
  let ruler: JobOptions["ruler"] = null;
  if (p.ruler.length > 0) {
    const [a, b] = p.ruler;
    const mm = Number(p.rulerMm);
    if (!a || !b) {
      return "Place both ruler points, or clear the ruler.";
    }
    if (!(mm > 0 && mm <= 1000)) {
      return "Enter the ruler distance in millimetres (more than 0, at most 1000).";
    }
    if (distance(a, b) < 2) {
      return "The two ruler points must be apart.";
    }
    if (
      photo &&
      ![a, b].every((pt) => pt.x >= 0 && pt.y >= 0 && pt.x <= photo.width && pt.y <= photo.height)
    ) {
      return `Both ruler points must lie on the photo (${photo.width} x ${photo.height} pixels).`;
    }
    ruler = [a.x, a.y, b.x, b.y, mm];
  }
  if (p.roi && (p.roi.width < 32 || p.roi.height < 32)) {
    return "The region must be at least 32 x 32 pixels.";
  }
  return {
    evidence,
    period,
    min_quality: p.minQuality,
    flip: p.flip,
    crop: p.crop,
    debug: p.debug,
    export: p.export,
    mirror: p.mirror,
    ppi: p.ppi,
    ruler,
    minutiae: p.minutiae,
    roi: p.roi ? [p.roi.x, p.roi.y, p.roi.width, p.roi.height] : null,
  };
}

interface Props {
  value: Params;
  onChange: (next: Params) => void;
  disabled: boolean;
  children?: ReactNode;
}

function Check({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) {
  return (
    <label className="check">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => {
          onChange(e.target.checked);
        }}
      />
      <span>{label}</span>
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

const whole = (e: ChangeEvent<HTMLInputElement>): number =>
  Math.max(0, Math.round(Number(e.target.value) || 0));

export function ParametersForm({ value: p, onChange, disabled, children }: Props) {
  const set = (patch: Partial<Params>) => {
    onChange({ ...p, ...patch });
  };
  const roi = p.roi ?? { x: 0, y: 0, width: 0, height: 0 };
  const setPoint = (index: 0 | 1, axis: "x" | "y", raw: string) => {
    const points = [p.ruler[0] ?? { x: 0, y: 0 }, p.ruler[1] ?? { x: 0, y: 0 }];
    const target = points[index];
    if (target) {
      points[index] = { ...target, [axis]: Number(raw) || 0 };
    }
    set({ ruler: points });
  };
  return (
    <fieldset className="params" disabled={disabled}>
      <legend>Extraction parameters</legend>
      <div className="params-grid">
        <label className="field">
          <span>Ridge period (px)</span>
          <input
            inputMode="decimal"
            placeholder="measure automatically"
            value={p.period}
            onChange={(e) => {
              set({ period: e.target.value });
            }}
          />
        </label>
        <label className="field">
          <span>Minimum quality: {p.minQuality.toFixed(2)}</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={p.minQuality}
            onChange={(e) => {
              set({ minQuality: Number(e.target.value) });
            }}
          />
        </label>
        <label className="field">
          <span>Export resolution (ppi)</span>
          <input
            type="number"
            min={250}
            max={2000}
            step={1}
            value={p.ppi}
            onChange={(e) => {
              set({ ppi: Number(e.target.value) });
            }}
          />
        </label>
      </div>
      <div className="params-checks">
        <Check
          label="Crop to the print"
          checked={p.crop}
          onChange={(v) => {
            set({ crop: v });
          }}
        />
        <Check
          label="Flip input"
          checked={p.flip}
          onChange={(v) => {
            set({ flip: v });
          }}
          hint="mirror the photo before extraction"
        />
        <Check
          label="Comparison export"
          checked={p.export}
          onChange={(v) => {
            set({ export: v });
          }}
          hint="dark ridges, scaled"
        />
        <Check
          label="Mirror export"
          checked={p.mirror}
          onChange={(v) => {
            set({ mirror: v });
          }}
          hint="contact-impression orientation"
        />
        <Check
          label="Debug images"
          checked={p.debug}
          onChange={(v) => {
            set({ debug: v });
          }}
        />
        <Check
          label="Minutiae (unvalidated)"
          checked={p.minutiae}
          onChange={(v) => {
            set({ minutiae: v });
          }}
        />
      </div>
      <div className="params-geometry">
        <fieldset className="subset">
          <legend>Region of interest (photo pixels)</legend>
          {(["x", "y", "width", "height"] as const).map((k) => (
            <label key={k} className="field field-narrow">
              <span>{k}</span>
              <input
                type="number"
                min={0}
                value={p.roi ? roi[k] : ""}
                placeholder="-"
                onChange={(e) => {
                  set({ roi: { ...roi, [k]: whole(e) } });
                }}
              />
            </label>
          ))}
          <button
            type="button"
            className="link"
            onClick={() => {
              set({ roi: null });
            }}
            disabled={!p.roi}
          >
            Whole photo
          </button>
        </fieldset>
        <fieldset className="subset">
          <legend>Ruler (two points on a scale in the photo)</legend>
          {([0, 1] as const).map((i) =>
            (["x", "y"] as const).map((axis) => (
              <label key={`${i}${axis}`} className="field field-narrow">
                <span>{`${axis}${i + 1}`}</span>
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={p.ruler[i]?.[axis] ?? ""}
                  placeholder="-"
                  onChange={(e) => {
                    setPoint(i, axis, e.target.value);
                  }}
                />
              </label>
            )),
          )}
          <label className="field field-narrow">
            <span>mm</span>
            <input
              inputMode="decimal"
              value={p.rulerMm}
              onChange={(e) => {
                set({ rulerMm: e.target.value });
              }}
            />
          </label>
          <button
            type="button"
            className="link"
            onClick={() => {
              set({ ruler: [] });
            }}
            disabled={p.ruler.length === 0}
          >
            No ruler
          </button>
        </fieldset>
      </div>
      {children}
    </fieldset>
  );
}
