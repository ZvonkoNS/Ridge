// What a job measured and produced, in the report's own terms. Ridge describes processing only:
// no score here is a match score, and the quality value is labelled indicative.
import { Hash } from "../components/ui";
import type { ExportInfo, Measurements, MinutiaeSummary, Quality } from "../ipc/types";

interface Props {
  result: {
    job_id: string;
    measurements: Measurements | null;
    export: ExportInfo | null;
    quality: Quality | null;
    minutiae?: MinutiaeSummary | null | undefined;
  };
}

const METHOD: Record<string, string> = {
  ruler: "ruler in the photo",
  "ridge-period": "ridge-period estimate (assumed ridge distance)",
  manual: "examiner value",
};

export function exportLine(exp: ExportInfo | null): string {
  if (exp === null) {
    return "not requested";
  }
  if (!exp.produced) {
    return `not produced: ${exp.reason}`;
  }
  const method = METHOD[exp.scale.method] ?? exp.scale.method;
  return `${exp.ppi} ppi, scale from ${method}, ±${exp.scale.uncertainty_pct.toFixed(exp.scale.uncertainty_pct < 1 ? 2 : 0)} %; ${exp.transforms.join(", ")}`;
}

export function JobSummary({ result }: Props) {
  const m = result.measurements;
  const nfiq = result.quality?.nfiq2;
  const minutiae = result.minutiae;
  return (
    <section className="summary" aria-label="Job result">
      <h3>
        Job <Hash value={result.job_id} length={8} />
      </h3>
      <dl>
        <dt>Ridge period</dt>
        <dd>{m ? `${m.ridge_period_px.toFixed(2)} px` : "-"}</dd>
        <dt>Finger located</dt>
        <dd>{m ? (m.found_finger ? "yes, by skin colour" : "no: the whole frame was used") : "-"}</dd>
        <dt>Comparison export</dt>
        <dd>{exportLine(result.export)}</dd>
        <dt>NFIQ 2</dt>
        <dd>
          {nfiq
            ? nfiq.computed
              ? `${nfiq.score} (${nfiq.label})`
              : `not computed: ${nfiq.reason}`
            : "not computed"}
        </dd>
        {minutiae ? (
          <>
            <dt>Minutiae</dt>
            <dd>
              {minutiae.produced
                ? `${minutiae.count} (${minutiae.endings} endings, ${minutiae.bifurcations} bifurcations); ${minutiae.label}`
                : `not produced: ${minutiae.reason}`}
            </dd>
          </>
        ) : null}
      </dl>
    </section>
  );
}
