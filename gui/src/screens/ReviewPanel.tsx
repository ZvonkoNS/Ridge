// Side-by-side review (FR-50): the original photo with region and ruler tools on the left (after a
// job also where its print was extracted), the job's outputs on the right, the photo's metadata
// under them (FR-36), the parameters below.
// Both images carry exhibit labels with their SHA-256; processed images say they are not an
// identification.
import { useState } from "react";

import { ExhibitLabel } from "../components/ExhibitLabel";
import { MeasureReadout, MeasureToggle, useMeasure } from "../components/Measure";
import { MinutiaeNote, MinutiaeToggle, useMinutiaeOverlay } from "../components/MinutiaeToggle";
import { StoredPhotoMetadata } from "../components/PhotoMetadata";
import { PrintAreaNote, PrintAreaShape, usePrintArea } from "../components/PrintArea";
import { ImageViewer, type Detail, type Tool } from "../components/ImageViewer";
import type { ScaleSource } from "../components/ScaleBar";
import { Button, Hash } from "../components/ui";
import { ipc, isLocked } from "../ipc/commands";
import { pngUrl } from "../ipc/images";
import type { Item, JobResult } from "../ipc/types";
import { usePreview } from "../lib/usePreview";
import { distance, type Rect } from "../lib/viewport";
import { DEFAULT_PARAMS, ParametersForm, referenceMm, toOptions, type Params } from "./ParametersForm";
import { JobSummary } from "./JobSummary";

// As ridge.export.transforms: the click error per point, the ID-1 size tolerance and the alignment allowance.
const CLICK_ERROR_PX = 1;
const CARD_EDGE_TOLERANCE_PCT = 0.15;
const CARD_ALIGNMENT_PCT = 2;

interface Props {
  evidence: Item;
  /** Every evidence photo of the case, for "Run on all photos". */
  allEvidence?: Item[];
  onFailure: (error: unknown) => void;
  onJobDone: () => void;
  notify?: (message: string) => void;
}

const TOOLS: { id: Tool; label: string }[] = [
  { id: "pan", label: "Move" },
  { id: "roi", label: "Draw region" },
  { id: "ruler", label: "Place ruler points" },
];

export function photoScale(params: Params, result: JobResult | null): ScaleSource | null {
  const [a, b] = params.ruler;
  const mm = referenceMm(params);
  if (a && b && mm > 0 && distance(a, b) >= 2) {
    const px = distance(a, b);
    const click = ((2 * CLICK_ERROR_PX) / px) * 100;
    return params.reference === "ruler"
      ? { pxPerMm: px / mm, method: "ruler", uncertaintyPct: click }
      : {
          pxPerMm: px / mm,
          method: "card",
          uncertaintyPct: click + CARD_EDGE_TOLERANCE_PCT + CARD_ALIGNMENT_PCT,
        };
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
  if (item.role === "export" || item.role === "export-gray") {
    return { pxPerMm: exp.ppi / 25.4, method: exp.scale.method, uncertaintyPct: exp.scale.uncertainty_pct };
  }
  if (item.role === "print" && result.measurements) {
    const pxPerMm = exp.scale.px_per_mm * result.measurements.output_scale;
    return { pxPerMm, method: exp.scale.method, uncertaintyPct: exp.scale.uncertainty_pct };
  }
  return null;
}

export function ReviewPanel({ evidence, allEvidence = [], onFailure, onJobDone, notify }: Props) {
  const [params, setParams] = useState<Params>(DEFAULT_PARAMS);
  const [tool, setTool] = useState<Tool>("pan");
  const [result, setResult] = useState<JobResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const measure = useMeasure();
  const [problem, setProblem] = useState<string | null>(null);
  const original = usePreview(evidence.sha256, onFailure);
  const images = result?.outputs.filter((o) => o.role !== "minutiae") ?? [];
  const current = images.find((o) => o.sha256 === selected) ?? images[0] ?? null;
  const output = usePreview(current?.sha256 ?? null, onFailure);
  const minutiaeSha = result?.outputs.find((o) => o.role === "minutiae")?.sha256 ?? null;
  const overlay = useMinutiaeOverlay(minutiaeSha, current?.role ?? null, output.source, onFailure);
  const printArea = usePrintArea(result);

  const loadDetail = async (rect: Rect): Promise<Detail> => {
    const region = await ipc.previewRegion(evidence.sha256, rect.x, rect.y, rect.width, rect.height);
    return {
      url: pngUrl(region.png_base64),
      rect: { x: region.x, y: region.y, width: region.width, height: region.height },
    };
  };

  const [batch, setBatch] = useState<{ done: number; total: number } | null>(null);

  /** The same settings on every photo, one job each; region and ruler belong to one photo and are left out. */
  const runAll = async () => {
    const options = toOptions(evidence.sha256, { ...params, roi: null, ruler: [] });
    if (typeof options === "string") {
      setProblem(options);
      return;
    }
    setProblem(null);
    const refused: string[] = [];
    setBatch({ done: 0, total: allEvidence.length });
    for (const [i, photo] of allEvidence.entries()) {
      try {
        await ipc.runJob({ ...options, evidence: photo.sha256 });
      } catch (error) {
        if (isLocked(error)) {
          setBatch(null);
          onFailure(error);
          return;
        }
        refused.push(`${photo.label}: ${error instanceof Error ? error.message : "refused"}`);
      }
      setBatch({ done: i + 1, total: allEvidence.length });
    }
    setBatch(null);
    onJobDone();
    const ok = allEvidence.length - refused.length;
    notify?.(
      `${ok} of ${allEvidence.length} jobs done; see Jobs for their signed reports.` +
        (refused.length ? ` Refused: ${refused.join("; ")}` : ""),
    );
  };

  const run = async () => {
    const options = toOptions(evidence.sha256, params, original.source);
    if (typeof options === "string") {
      setProblem(options);
      return;
    }
    setProblem(null);
    setRunning(true);
    try {
      const done = await ipc.runJob(options);
      setResult(done);
      measure.reset(); // points belong to the previous output
      const preferred =
        done.outputs.find((o) => o.role === "export-gray") ??
        done.outputs.find((o) => o.role === "export") ??
        done.outputs.find((o) => o.role === "print");
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
        const done = await ipc.exportItem(current.sha256, current.label);
        notify?.(
          done.format
            ? `Exported as ${done.format.toUpperCase()} (SHA-256 of the file ${done.sha256?.slice(0, 12) ?? ""}); the export is in the custody log.`
            : "Exported as stored; the export is in the custody log.",
        );
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
          <PrintAreaNote overlay={printArea} />
          <ImageViewer
            title="Original photo"
            url={original.url}
            bitmap={original.bitmap}
            source={original.source}
            tool={tool}
            roi={params.roi}
            ruler={params.ruler}
            overlay={
              printArea.on && printArea.area ? (
                <PrintAreaShape area={printArea.area} size={original.source} />
              ) : null
            }
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
                  measure.reset();
                }}
              >
                {o.role === "debug" ? o.label : o.role}
              </button>
            ))}
            <MinutiaeToggle overlay={overlay} />
            {current ? <MeasureToggle measuring={measure.measuring} onToggle={measure.toggle} /> : null}
          </div>
          <MinutiaeNote overlay={overlay} />
          {measure.measuring && current && result ? (
            <MeasureReadout points={measure.points} scale={outputScale(current, result)} />
          ) : null}
          {current && result ? (
            <ImageViewer
              title={`${current.role} output`}
              url={output.url}
              bitmap={output.bitmap}
              source={output.source}
              marks={overlay.marks}
              {...measure.viewer}
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
      <StoredPhotoMetadata sha256={evidence.sha256} onFailure={onFailure} />
      <ParametersForm value={params} onChange={setParams} disabled={running}>
        <div className="params-actions">
          {problem ? (
            <p className="field-error" role="alert">
              {problem}
            </p>
          ) : null}
          <Button variant="primary" onClick={() => void run()} busy={running} disabled={batch !== null}>
            {running ? "Running job..." : "Run job"}
          </Button>
          {allEvidence.length > 1 ? (
            <Button
              onClick={() => void runAll()}
              busy={batch !== null}
              disabled={running}
              title="Region and ruler belong to one photo and are left out"
            >
              {batch
                ? `Job ${Math.min(batch.done + 1, batch.total)} of ${batch.total}...`
                : `Run on all ${allEvidence.length} photos`}
            </Button>
          ) : null}
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
