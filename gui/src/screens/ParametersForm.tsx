// Extraction parameters. Every value sent with a job is visible here and recorded in the signed
// report; the region and the ruler can be drawn on the photo or typed (no dragging required,
// WCAG 2.2 SC 2.5.7).
import type { ChangeEvent, ReactNode } from "react";

import type { Channel, JobOptions, ReferenceKind } from "../ipc/types";
import { Check } from "../components/Check";
import { MethodVariants } from "./MethodVariants";
import { distance, type Point, type Rect, type Size } from "../lib/viewport";

/** Edge lengths of an ISO/IEC 7810 ID-1 card (bank, ID and driving-licence cards), as ridge.export.transforms. */
export const REFERENCE_MM: Record<ReferenceKind, number | null> = {
  ruler: null,
  "id1-long": 85.6,
  "id1-short": 53.98,
};

export const REFERENCE_LABELS: Record<ReferenceKind, string> = {
  ruler: "Ruler or scale (type the distance)",
  "id1-long": "ID-1 card, long edge: 85.60 mm",
  "id1-short": "ID-1 card, short edge: 53.98 mm",
};

/** Shown before a job while no two reference points are placed (FR-31; product owner, 2026-10-24). */
export const NO_REFERENCE_HINT =
  "No scale reference: the export scale will be estimated from the ridge spacing (±15 %). If possible, add a " +
  "ruler or an ID-1 (bank-size) card in the plane of the finger pad and mark two points on it; otherwise proceed as is.";

/** ANSI/NIST-ITL finger position codes (0 unknown, 1-5 right thumb to little, 6-10 left), as ridge.case.submission. */
export const FINGER_POSITIONS: readonly string[] = [
  "unknown",
  "right thumb",
  "right index",
  "right middle",
  "right ring",
  "right little",
  "left thumb",
  "left index",
  "left middle",
  "left ring",
  "left little",
];

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
  reference: ReferenceKind;
  fingerPosition: number;
  sourceAgency: string;
  channel: Channel;
  specularMask: boolean;
  upright: boolean;
  localFrequency: boolean;
  rectify: boolean;
}

/** The distance the form sends: the typed millimetres for a ruler, the standard edge length for a card. */
export function referenceMm(p: Pick<Params, "reference" | "rulerMm">): number {
  return REFERENCE_MM[p.reference] ?? Number(p.rulerMm);
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
  reference: "ruler",
  fingerPosition: 0,
  sourceAgency: "",
  channel: "green",
  specularMask: false,
  upright: false,
  localFrequency: false,
  rectify: false,
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
    const mm = referenceMm(p);
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
  const agency = p.sourceAgency.trim();
  if (agency.length > 200) {
    return "The source agency must be at most 200 characters.";
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
    // No points: the engine estimates the scale, and it refuses a card kind without points (also what
    // "Run on all photos" sends, since the points belong to one photo).
    reference: ruler === null ? "ruler" : p.reference,
    minutiae: p.minutiae,
    roi: p.roi ? [p.roi.x, p.roi.y, p.roi.width, p.roi.height] : null,
    finger_position: p.fingerPosition,
    source_agency: agency === "" ? null : agency,
    options: {
      channel: p.channel,
      specular_mask: p.specularMask,
      upright: p.upright,
      local_frequency: p.localFrequency,
      rectify: p.rectify,
    },
  };
}

interface Props {
  value: Params;
  onChange: (next: Params) => void;
  disabled: boolean;
  /** Research mode (ADR-015): the unvalidated method variants are shown and editable only when true. */
  research?: boolean;
  children?: ReactNode;
}

/** The variant fields of ADR-014 at their defaults: what leaving research mode puts back. */
export function withoutVariants(p: Params): Params {
  return {
    ...p,
    channel: DEFAULT_PARAMS.channel,
    specularMask: DEFAULT_PARAMS.specularMask,
    upright: DEFAULT_PARAMS.upright,
    localFrequency: DEFAULT_PARAMS.localFrequency,
    rectify: DEFAULT_PARAMS.rectify,
  };
}

const whole = (e: ChangeEvent<HTMLInputElement>): number =>
  Math.max(0, Math.round(Number(e.target.value) || 0));

export function ParametersForm({ value: p, onChange, disabled, research = false, children }: Props) {
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
      {research ? <MethodVariants value={p} onChange={set} /> : null}
      <fieldset className="subset">
        <legend>Submission record (your statements, recorded in the report)</legend>
        <label className="field">
          <span>Finger shown</span>
          <select
            value={p.fingerPosition}
            onChange={(e) => {
              set({ fingerPosition: Math.min(10, Math.max(0, Math.round(Number(e.target.value) || 0))) });
            }}
          >
            {FINGER_POSITIONS.map((name, code) => (
              <option key={code} value={code}>
                {code}: {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Source agency</span>
          <input
            value={p.sourceAgency}
            maxLength={200}
            placeholder="not stated"
            onChange={(e) => {
              set({ sourceAgency: e.target.value });
            }}
          />
        </label>
      </fieldset>
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
          <legend>Scale reference (two points on a ruler or an ID-1 card in the photo)</legend>
          <label className="field">
            <span>Object</span>
            <select
              value={p.reference}
              onChange={(e) => {
                const kind = e.target.value;
                if (kind in REFERENCE_MM) {
                  set({ reference: kind as ReferenceKind });
                }
              }}
            >
              {(Object.keys(REFERENCE_LABELS) as ReferenceKind[]).map((k) => (
                <option key={k} value={k}>
                  {REFERENCE_LABELS[k]}
                </option>
              ))}
            </select>
          </label>
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
              value={p.reference === "ruler" ? p.rulerMm : String(REFERENCE_MM[p.reference])}
              disabled={p.reference !== "ruler"}
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
            Clear points
          </button>
        </fieldset>
      </div>
      {p.ruler.length < 2 ? (
        <p className="muted" role="note">
          {NO_REFERENCE_HINT}
        </p>
      ) : null}
      {children}
    </fieldset>
  );
}
