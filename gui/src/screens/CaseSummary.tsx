// A one-screen summary of the open case, from the verified custody log: what is stored, how jobs
// ended, notes, and when the case was last verified or its custody head exported.
import { useEffect, useState } from "react";

import { utc } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { CaseStatus } from "../ipc/types";

const ROLE: Record<string, string> = {
  evidence: "evidence photo(s)",
  reference: "reference image(s)",
  print: "processed print(s)",
  export: "comparison export(s)",
  minutiae: "minutiae file(s)",
  debug: "debug image(s)",
};

function counts(values: Record<string, number>, names: Record<string, string> = {}): string {
  const parts = Object.entries(values).map(([key, n]) => `${String(n)} ${names[key] ?? key}`);
  return parts.length > 0 ? parts.join(", ") : "none";
}

export function CaseSummary({
  refresh,
  onFailure,
}: {
  refresh: unknown;
  onFailure: (error: unknown) => void;
}) {
  const [status, setStatus] = useState<CaseStatus | null>(null);
  useEffect(() => {
    ipc.caseStatus().then(setStatus, onFailure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);
  if (status === null) {
    return null;
  }
  return (
    <section className="card" aria-labelledby="summary-title">
      <h2 id="summary-title">Case summary</h2>
      <dl className="report-meta">
        <dt>Stored</dt>
        <dd>{counts(status.items, ROLE)}</dd>
        <dt>Jobs</dt>
        <dd>
          {counts(status.jobs)}; {status.signed_reports} signed report(s)
        </dd>
        <dt>Notes</dt>
        <dd>{status.notes}</dd>
        <dt>Verified</dt>
        <dd>
          {status.last_verified
            ? `${utc(status.last_verified)} (${status.last_verify_result ?? ""})`
            : "never"}
        </dd>
        <dt>Custody head exported</dt>
        <dd>{status.last_head_export ? utc(status.last_head_export) : "never"}</dd>
        <dt>Custody log</dt>
        <dd>{status.entries} entries</dd>
      </dl>
    </section>
  );
}
