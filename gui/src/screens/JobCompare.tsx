// Compare the recorded settings of two jobs: which parameters, input and Ridge version differ.
// Both reports are verified by the core before they are shown (each read is logged). This compares
// settings only; it says nothing about which output is better.
import { useState } from "react";

import { Hash, utc } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { JobRecord, JobReport } from "../ipc/types";
import { parameterText } from "./ParameterList";

interface Row {
  name: string;
  here: string;
  there: string;
}

/** Every recorded setting that differs between two reports, in a stable order. */
export function differences(a: JobReport, b: JobReport): { rows: Row[]; same: number } {
  const rows: Row[] = [];
  const add = (name: string, here: unknown, there: unknown) => {
    const [x, y] = [parameterText(here), parameterText(there)];
    if (x !== y) {
      rows.push({ name, here: x, there: y });
    }
  };
  add("input (SHA-256)", a.input.sha256, b.input.sha256);
  add("Ridge version", a.ridge.version, b.ridge.version);
  add("platform", `${a.ridge.platform} (${a.ridge.machine})`, `${b.ridge.platform} (${b.ridge.machine})`);
  const keys = [...new Set([...Object.keys(a.parameters), ...Object.keys(b.parameters)])].sort();
  for (const key of keys) {
    add(key, a.parameters[key], b.parameters[key]);
  }
  return { rows, same: keys.length + 3 - rows.length };
}

interface Props {
  report: JobReport;
  jobs: JobRecord[];
  onFailure: (error: unknown) => void;
}

export function JobCompare({ report, jobs, onFailure }: Props) {
  const others = jobs.filter((j) => j.report_sha256 && j.job_id !== report.job_id);
  const [other, setOther] = useState<JobReport | null>(null);
  if (others.length === 0) {
    return null;
  }

  const choose = async (jobId: string) => {
    if (!jobId) {
      setOther(null);
      return;
    }
    try {
      setOther((await ipc.getReport(jobId)).report);
    } catch (error) {
      onFailure(error);
    }
  };
  const diff = other ? differences(report, other) : null;

  return (
    <section className="job-compare" aria-label="Compare settings with another job">
      <label className="field">
        <span>Compare settings with</span>
        <select
          value={other?.job_id ?? ""}
          onChange={(e) => {
            void choose(e.target.value);
          }}
        >
          <option value="">another job...</option>
          {others.map((j) => (
            <option key={j.job_id} value={j.job_id}>
              {utc(j.started_utc)} · job {j.job_id.slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      {other && diff ? (
        diff.rows.length === 0 ? (
          <p>The two jobs were run with the same input and settings.</p>
        ) : (
          <table className="compare-table">
            <caption>
              Settings that differ ({diff.same} the same). Comparing settings does not rank the outputs.
            </caption>
            <thead>
              <tr>
                <th scope="col">Setting</th>
                <th scope="col">This job</th>
                <th scope="col">
                  Job <Hash value={other.job_id} length={8} />
                </th>
              </tr>
            </thead>
            <tbody>
              {diff.rows.map((r) => (
                <tr key={r.name}>
                  <th scope="row">{r.name}</th>
                  <td>
                    <code>{r.here}</code>
                  </td>
                  <td>
                    <code>{r.there}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : null}
    </section>
  );
}
