// What a job measured and produced, in the report's own terms. Ridge describes processing only:
// no score here is a match score, and the quality value is labelled indicative.
import { areaLine } from "../components/PrintArea";
import { Hash } from "../components/ui";
import type {
  ExportInfo,
  LimitsSection,
  Measurements,
  MinutiaeSummary,
  Quality,
  SubmissionRecord,
} from "../ipc/types";

interface Props {
  result: {
    job_id: string;
    measurements: Measurements | null;
    export: ExportInfo | null;
    quality: Quality | null;
    minutiae?: MinutiaeSummary | null | undefined;
    limits_of_use?: LimitsSection | null | undefined;
    submission?: SubmissionRecord | null | undefined;
  };
}

/** The submission record as one line (FR-38); absent in reports made before it. */
export function submissionLine(record: SubmissionRecord | null | undefined): string | null {
  if (!record) {
    return null;
  }
  const agency = record.source_agency ?? "not stated";
  const device = record.capture_device ?? "none named in the file";
  return `finger position ${String(record.finger_position)} (${record.finger}); source agency ${agency}; capture device ${device} (${record.capture_device_note})`;
}

/** The limits-of-use outcome of a job (PRD §12 item 8); warnings stand out, nothing is refused. */
export function LimitsOutcome({ section }: { section: LimitsSection | null | undefined }) {
  if (!section) {
    return null;
  }
  if (!section.configured) {
    return <p className="muted">No limits of use are configured for this store.</p>;
  }
  const signer =
    section.signed_by === undefined
      ? ""
      : section.signed_by
        ? `, signed with key ${section.signed_by.key_id}`
        : ", not signed";
  if (section.within) {
    return (
      <p className="badge badge-ok">
        Within the limits of use ({section.source}
        {signer})
      </p>
    );
  }
  return (
    <div className="notice notice-caution" role="status">
      <div className="notice-body">
        <strong>Outside the limits of use</strong> ({section.source}
        {signer}):
        <ul className="limits-warnings">
          {section.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

const METHOD: Record<string, string> = {
  ruler: "ruler in the photo",
  card: "card edge in the photo",
  "ridge-period": "ridge-period estimate (assumed ridge distance)",
  manual: "examiner value",
};

/** The notice of an export scaled without a reference object (FR-31); the job went ahead regardless. */
export function ScaleNotice({ exp }: { exp: ExportInfo | null | undefined }) {
  if (!exp?.produced || !exp.scale.notice) {
    return null;
  }
  return (
    <div className="notice notice-caution" role="status">
      <div className="notice-body">
        <strong>No scale reference.</strong> {exp.scale.notice}
      </div>
    </div>
  );
}

export function exportLine(exp: ExportInfo | null): string {
  if (exp === null) {
    return "not requested";
  }
  if (!exp.produced) {
    return `not produced: ${exp.reason}`;
  }
  const method = METHOD[exp.scale.method] ?? exp.scale.method;
  const where = exp.scale.reference ? ` (${exp.scale.reference})` : "";
  const twin = exp.grayscale ? `; grayscale twin ${exp.grayscale.sha256.slice(0, 12)}` : "";
  return `${exp.ppi} ppi, scale from ${method}${where}, ±${exp.scale.uncertainty_pct.toFixed(exp.scale.uncertainty_pct < 1 ? 2 : 0)} %; ${exp.transforms.join(", ")}${twin}`;
}

/** The method variants a job used, from its measurements (ADR-014); null when none was on. */
export function variantsLine(m: Measurements | null): string | null {
  if (!m) {
    return null;
  }
  const parts: string[] = [];
  if (m.channel_used !== undefined && m.channel_used !== "green") {
    parts.push(`plane ${m.channel_used}`);
  }
  if (m.specular_fraction != null) {
    parts.push(`specular mask removed ${(100 * m.specular_fraction).toFixed(1)} % of the finger`);
  }
  if (m.upright_rotation_deg != null) {
    parts.push(`rotated ${m.upright_rotation_deg.toFixed(1)}° to upright`);
  }
  if (m.local_period_px) {
    const s = m.local_period_px;
    parts.push(`local spacing ${s.min.toFixed(1)} to ${s.max.toFixed(1)} px (median ${s.median.toFixed(1)})`);
  }
  return parts.length > 0 ? `${parts.join("; ")} (unvalidated variants, ADR-014)` : null;
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
      <LimitsOutcome section={result.limits_of_use} />
      <ScaleNotice exp={result.export} />
      {result.export?.produced && result.export.resolution_note ? (
        <p className="muted" role="note">
          {result.export.resolution_note}
        </p>
      ) : null}
      <dl>
        <dt>Ridge period</dt>
        <dd>{m ? `${m.ridge_period_px.toFixed(2)} px` : "-"}</dd>
        <dt>Finger located</dt>
        <dd>{m ? (m.found_finger ? "yes, by skin colour" : "no: the whole frame was used") : "-"}</dd>
        {variantsLine(m) ? (
          <>
            <dt>Variants</dt>
            <dd>{variantsLine(m)}</dd>
          </>
        ) : null}
        <dt>Print area</dt>
        <dd>{m ? areaLine(m.print_area) : "-"}</dd>
        {result.submission ? (
          <>
            <dt>Submission</dt>
            <dd>{submissionLine(result.submission)}</dd>
          </>
        ) : null}
        <dt>Comparison export</dt>
        <dd>{exportLine(result.export)}</dd>
        <dt>NFIQ 2</dt>
        <dd>
          {nfiq
            ? nfiq.computed
              ? `${nfiq.score} (${nfiq.label})${nfiq.image ? ` on the ${nfiq.image} image` : ""}`
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
