// Side-by-side review (FR-50): the original photo with region and ruler tools on the left, the
// job's outputs on the right, the parameters below. Both images carry exhibit labels with their
// SHA-256; processed images say they are not an identification.
import { useState } from "react";

import { ExhibitLabel } from "../components/ExhibitLabel";
import { ImageViewer, type Detail, type Tool } from "../components/ImageViewer";
import type { ScaleSource } from "../components/ScaleBar";
import { Button, Hash } from "../components/ui";
import { ipc } from "../ipc/commands";
import { pngUrl } from "../ipc/images";
import type { Item, JobResult } from "../ipc/types";
import { usePreview } from "../lib/usePreview";
import { distance, type Rect } from "../lib/viewport";
import { DEFAULT_PARAMS, ParametersForm, toOptions, type Params } from "./ParametersForm";
import { JobSummary } from "./JobSummary";

const CLICK_ERROR_PX = 1; // as ridge.export.transforms.CLICK_ERROR_PX

interface Props {
  evidence: Item;
  onFailure: (error: unknown) => void;
  onJobDone: () => void;
}

const TOOLS: { id: Tool; label: string }[] = [
  { id: "pan", label: "Move" },
  { id: "roi", label: "Draw region" },
  { id: "ruler", label: "Place ruler points" },
];

export function photoScale(params: Params, result: JobResult | null): ScaleSource | null {
  const [a, b] = params.ruler;
  const mm = Number(params.rulerMm);
  if (a && b && mm > 0 && distance(a, b) >= 2) {
    const px = distance(a, b);
    return { pxPerMm: px / mm, method: "ruler", uncertaintyPct: ((2 * CLICK_ERROR_PX) / px) * 100 };
  }
  if (result?.export?.produced) {
    const s = result.export.scale;
    return { pxPerMm: s.px_per_mm, method: s.method, uncertaintyPct: s.uncertainty_pct };
  }
  return null;
}

export function outputScale(
  item: Item,
  result: Pick<JobResult, "export" | "measurements">,
): ScaleSource | null {
  const exp = result.export?.produced ? result.export : null;
  if (!exp) {
    return null;
  }
  if (item.role === "export") {
    return { pxPerMm: exp.ppi / 25.4, method: exp.scale.method, uncertaintyPct: exp.scale.uncertainty_pct };
  }
  if (item.role === "print" && result.measurements) {
    const pxPerMm = exp.scale.px_per_mm * result.measurements.output_scale;
    return { pxPerMm, method: exp.scale.method, uncertaintyPct: exp.scale.uncertainty_pct };
  }
  return null;
}

export function ReviewPanel({ evidence, onFailure, onJobDone }: Props) {
  const [params, setParams] = useState<Params>(DEFAULT_PARAMS);
  const [tool, setTool] = useState<Tool>("pan");
  const [result, setResult] = useState<JobResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const original = usePreview(evidence.sha256, onFailure);
  const images = result?.outputs.filter((o) => o.role !== "minutiae") ?? [];
  const current = images.find((o) => o.sha256 === selected) ?? images[0] ?? null;
  const output = usePreview(current?.sha256 ?? null, onFailure);

  const loadDetail = async (rect: Rect): Promise<Detail> => {
    const region = await ipc.previewRegion(evidence.sha256, rect.x, rect.y, rect.width, rect.height);
    return {
      url: pngUrl(region.png_base64),
      rect: { x: region.x, y: region.y, width: region.width, height: region.height },
    };
  };

  const run = async () => {
    const options = toOptions(evidence.sha256, params);
    if (typeof options === "string") {
      setProblem(options);
      return;
    }
    setProblem(null);
    setRunning(true);
    try {
      const done = await ipc.runJob(options);
      setResult(done);
      const preferred =
        done.outputs.find((o) => o.role === "export") ?? done.outputs.find((o) => o.role === "print");
      setSelected(preferred?.sha256 ?? null);
      onJobDone();
    } catch (error) {
      onFailure(error);
    } finally {
      setRunning(false);
    }
  };

  const exportCurrent = async () => {
    if (current) {
      try {
        await ipc.exportItem(current.sha256, current.label);
        onJobDone();
      } catch (error) {
        onFailure(error);
      }
    }
  };

  const scale = photoScale(params, result);
  return (
    <div className="review">
      <div className="review-pair">
        <div className="review-side">
          <div className="toolbar" role="radiogroup" aria-label="Pointer tool on the original photo">
            {TOOLS.map((t) => (
              <label key={t.id} className={`tool${tool === t.id ? " tool-on" : ""}`}>
                <input
                  type="radio"
                  name="tool"
                  value={t.id}
                  checked={tool === t.id}
                  onChange={() => {
                    setTool(t.id);
                  }}
                />
                {t.label}
              </label>
            ))}
          </div>
          <ImageViewer
            title="Original photo"
            url={original.url}
            bitmap={original.bitmap}
            source={original.source}
            tool={tool}
            roi={params.roi}
            ruler={params.ruler}
            onRoi={(roi) => {
              setParams((p) => ({ ...p, roi }));
            }}
            onRulerPoint={(pt) => {
              setParams((p) => ({ ...p, ruler: p.ruler.length >= 2 ? [pt] : [...p.ruler, pt] }));
            }}
            loadDetail={loadDetail}
            label={(zoom) => (
              <ExhibitLabel
                role="evidence"
                sha256={evidence.sha256}
                detail={evidence.source ?? evidence.label}
                scale={scale}
                zoom={zoom}
              />
            )}
          />
        </div>
        <div className="review-side">
          <div className="toolbar" role="group" aria-label="Outputs of the job">
            {images.length === 0 ? (
              <span className="toolbar-note">Run a job to see its outputs here.</span>
            ) : null}
            {images.map((o) => (
              <button
                key={o.sha256}
                type="button"
                aria-pressed={o.sha256 === current?.sha256}
                className={`tab${o.sha256 === current?.sha256 ? " tab-on" : ""}`}
                onClick={() => {
                  setSelected(o.sha256);
                }}
              >
                {o.role === "debug" ? o.label : o.role}
              </button>
            ))}
          </div>
          {current && result ? (
            <ImageViewer
              title={`${current.role} output`}
              url={output.url}
              bitmap={output.bitmap}
              source={output.source}
              label={(zoom) => (
                <ExhibitLabel
                  role={current.role}
                  sha256={current.sha256}
                  detail={current.label}
                  scale={outputScale(current, result)}
                  zoom={zoom}
                />
              )}
            />
          ) : (
            <div className="viewer-placeholder">No output yet</div>
          )}
        </div>
      </div>
      <ParametersForm value={params} onChange={setParams} disabled={running}>
        <div className="params-actions">
          {problem ? (
            <p className="field-error" role="alert">
              {problem}
            </p>
          ) : null}
          <Button variant="primary" onClick={() => void run()} busy={running}>
            {running ? "Running job..." : "Run job"}
          </Button>
          <Button onClick={() => void exportCurrent()} disabled={!current || running}>
            Export shown image
          </Button>
        </div>
      </ParametersForm>
      {result ? <JobSummary result={result} /> : null}
      <p className="review-foot">
        Evidence <Hash value={evidence.sha256} /> · the original is never modified; every job is logged and
        signed.
      </p>
    </div>
  );
}
