// Jobs from the custody log; a report is shown only after its hash and signature verify (FR-28),
// can be exported with its detached signature, and a job can be reproduced (FR-34, NFR-3).
import { useEffect, useState } from "react";

import { ExhibitLabel } from "../components/ExhibitLabel";
import { ImageViewer } from "../components/ImageViewer";
import { MinutiaeNote, MinutiaeToggle, useMinutiaeOverlay } from "../components/MinutiaeToggle";
import { NotesPanel } from "../components/NotesPanel";
import { Button, Hash, Notice, StaggerItem, StaggerList, utc } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { Item, JobRecord, Reproduction, VerifiedReport } from "../ipc/types";
import { usePreview } from "../lib/usePreview";
import { JobSummary } from "./JobSummary";
import { outputScale } from "./ReviewPanel";

interface Props {
  items: Item[];
  onFailure: (error: unknown) => void;
  onChanged: () => void;
  notify: (message: string) => void;
}

/** A recorded parameter value as text: none, a scalar, or compact JSON for lists and objects. */
export function parameterText(value: unknown): string {
  if (value === null || value === undefined) {
    return "none";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

/** Every recorded parameter, exactly as signed. */
export function ParameterList({ parameters }: { parameters: Record<string, unknown> }) {
  return (
    <ul className="paramlist">
      {Object.entries(parameters).map(([key, value]) => (
        <li key={key}>
          <span className="paramlist-key">{key}</span> <code>{parameterText(value)}</code>
        </li>
      ))}
    </ul>
  );
}

function ReportView({ shown, items, onFailure, onChanged, notify }: { shown: VerifiedReport } & Props) {
  const report = shown.report;
  const images = report.outputs.filter((o) => o.role !== "minutiae");
  const [selected, setSelected] = useState(images[0]?.sha256 ?? null);
  const [reproduction, setReproduction] = useState<Reproduction | null>(null);
  const [busy, setBusy] = useState<"export" | "reproduce" | null>(null);
  const current = images.find((o) => o.sha256 === selected) ?? null;
  const preview = usePreview(current?.sha256 ?? null, onFailure);
  const minutiaeSha = report.outputs.find((o) => o.role === "minutiae")?.sha256 ?? null;
  const overlay = useMinutiaeOverlay(minutiaeSha, current?.role ?? null, preview.source, onFailure);
  const item = items.find((i) => i.sha256 === current?.sha256);
  const result = report;

  const act = async (what: "export" | "reproduce") => {
    setBusy(what);
    try {
      if (what === "export") {
        const done = await ipc.exportReport(report.job_id);
        notify(`Signed report exported with its signature (${done.signature.split(/[\\/]/).pop() ?? ""}).`);
      } else {
        setReproduction(await ipc.reproduceJob(report.job_id));
        onChanged();
      }
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className="report" aria-label={`Report of job ${report.job_id.slice(0, 8)}`}>
      <header className="report-head">
        <p className="badge badge-ok">Signature verified · key {shown.key_id}</p>
        <div className="report-actions">
          <Button onClick={() => void act("export")} busy={busy === "export"}>
            Export signed report...
          </Button>
          <Button onClick={() => void act("reproduce")} busy={busy === "reproduce"}>
            Reproduce job
          </Button>
        </div>
      </header>
      {reproduction ? (
        <Notice tone={reproduction.identical ? "ok" : "caution"}>
          {reproduction.identical
            ? `Reproduced bit for bit as job ${reproduction.new_job.slice(0, 8)}: every output has the same SHA-256.`
            : `Job ${reproduction.new_job.slice(0, 8)} differs: ${reproduction.differing.length} differing, ${reproduction.missing.length} missing, ${reproduction.extra.length} extra outputs.`}
          {Object.keys(reproduction.environment_changes).length > 0
            ? ` Environment changes: ${Object.keys(reproduction.environment_changes).join(", ")} (results are reproducible per OS and CPU architecture).`
            : ""}
        </Notice>
      ) : null}
      <JobSummary result={result} />
      <dl className="report-meta">
        <dt>Created</dt>
        <dd>{utc(report.created_utc)}</dd>
        <dt>Input</dt>
        <dd>
          {report.input.label} <Hash value={report.input.sha256} />{" "}
          {report.input.source ? `· ${report.input.source}` : ""}
        </dd>
        <dt>Ridge</dt>
        <dd>
          {report.ridge.version} · Python {report.ridge.python} · {report.ridge.platform} (
          {report.ridge.machine})
        </dd>
        <dt>Parameters</dt>
        <dd>
          <ParameterList parameters={report.parameters} />
        </dd>
      </dl>
      <p className="disclaimer">{report.disclaimer}</p>
      {current && item ? (
        <>
          <div className="toolbar" role="group" aria-label="Outputs of this job">
            {images.map((o) => (
              <button
                key={o.sha256}
                type="button"
                aria-pressed={o.sha256 === selected}
                className={`tab${o.sha256 === selected ? " tab-on" : ""}`}
                onClick={() => {
                  setSelected(o.sha256);
                }}
              >
                {o.role === "debug" ? o.label : o.role}
              </button>
            ))}
            <MinutiaeToggle overlay={overlay} />
          </div>
          <MinutiaeNote overlay={overlay} />
          <ImageViewer
            title={`${current.role} output of the job`}
            url={preview.url}
            bitmap={preview.bitmap}
            source={preview.source}
            marks={overlay.marks}
            label={(zoom) => (
              <ExhibitLabel
                role={current.role}
                sha256={current.sha256}
                detail={current.label}
                scale={outputScale(item, result)}
                zoom={zoom}
              />
            )}
          />
        </>
      ) : null}
      <NotesPanel jobId={report.job_id} onFailure={onFailure} />
    </article>
  );
}

export function JobsSection(props: Props) {
  const { items, onFailure } = props;
  const [jobs, setJobs] = useState<JobRecord[] | null>(null);
  const [shown, setShown] = useState<VerifiedReport | null>(null);
  const labels = new Map(items.map((i) => [i.sha256, i.label]));

  useEffect(() => {
    ipc.listJobs().then(setJobs, onFailure);
    // reload when the stored items change (a new job adds outputs)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);

  const open = async (job: JobRecord) => {
    try {
      setShown(await ipc.getReport(job.job_id));
    } catch (error) {
      onFailure(error);
    }
  };

  return (
    <div className="section">
      <aside className="section-list">
        <h2>Jobs</h2>
        {jobs === null ? <p className="empty">Reading the custody log...</p> : null}
        {jobs?.length === 0 ? <p className="empty">No jobs yet. Run one from an evidence photo.</p> : null}
        {jobs && jobs.length > 0 ? (
          <StaggerList className="picklist" label="Jobs">
            {[...jobs].reverse().map((job) => (
              <StaggerItem key={job.job_id}>
                <button
                  type="button"
                  className={`pick${shown?.job_id === job.job_id ? " pick-on" : ""}`}
                  aria-pressed={shown?.job_id === job.job_id}
                  disabled={!job.report_sha256}
                  onClick={() => void open(job)}
                >
                  <span className="pick-title">
                    {utc(job.started_utc)} <span className={`state state-${job.result}`}>{job.result}</span>
                  </span>
                  <span className="pick-sub">
                    {labels.get(job.evidence_sha256) ?? job.evidence_sha256.slice(0, 12)}
                  </span>
                  <span className="pick-meta">
                    job <Hash value={job.job_id} length={8} />
                    {job.error ? ` · ${job.error}` : ""}
                  </span>
                </button>
              </StaggerItem>
            ))}
          </StaggerList>
        ) : null}
      </aside>
      <div className="section-main">
        {shown ? (
          <ReportView key={shown.job_id} shown={shown} {...props} />
        ) : (
          <p className="empty empty-main">Choose a job to see its verified report.</p>
        )}
      </div>
    </div>
  );
}
