// The store's case list, with the details read by "Show case details" and the outcome of
// "Verify all cases". References, legal bases and retention dates are encrypted per case, so the
// list shows only case ids until the examiner enters the passphrase.
import { Button, Hash, Notice, StaggerItem, StaggerList, utc } from "../components/ui";
import type { CaseOverview, CaseSummary, StoreCheck } from "../ipc/types";

const STATE_TEXT: Record<CaseSummary["state"], string> = {
  active: "ready",
  locked: "open in another Ridge window",
  erasing: "disposal interrupted",
  disposed: "disposed",
  invalid: "unreadable",
};

/** The outcome of "Verify all cases": every case named, failures with their problems. */
export function StoreChecks({ checks }: { checks: StoreCheck[] }) {
  const checked = checks.filter((c) => c.checked);
  const failed = checks.filter((c) => !c.ok);
  return (
    <Notice tone={failed.length ? "error" : "ok"}>
      {checked.filter((c) => c.ok).length} of {checked.length} cases verified
      {failed.length ? `; ${failed.length} with problems` : ""}.
      <ul className="limits-warnings">
        {checks.map((c) => (
          <li key={c.case_id}>
            <Hash value={c.case_id} length={8} /> {c.reference ?? ""}{" "}
            {c.checked && c.ok
              ? `verified: ${c.items} items, ${c.reports} signed reports`
              : `${c.checked ? "FAILED" : c.ok ? "not checked" : "NOT CHECKED"}: ${c.problems.join("; ")}`}
          </li>
        ))}
      </ul>
    </Notice>
  );
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** What the overview knows about one case, below its row. */
function Details({ details }: { details: CaseOverview }) {
  if (details.reference === null) {
    return details.problem ? <p className="case-row-detail">Details not read: {details.problem}</p> : null;
  }
  return (
    <p className="case-row-detail">
      <span>Keep until {details.retention_until}</span>
      <span>{plural(details.evidence ?? 0, "evidence photo", "evidence photos")}</span>
      <span>{plural(details.jobs ?? 0, "job", "jobs")}</span>
      {details.legal_hold ? <span className="badge badge-hold">Legal hold</span> : null}
      {details.due ? <span className="badge badge-due">Retention date reached</span> : null}
    </p>
  );
}

interface ListProps {
  cases: CaseSummary[];
  details: Map<string, CaseOverview> | null;
  busy: string | null;
  onUnlock: (caseId: string) => void;
}

export function CaseList({ cases, details, busy, onUnlock }: ListProps) {
  return (
    <StaggerList className="caselist" label="Cases">
      {cases.map((c) => {
        const known = details?.get(c.case_id);
        return (
          <StaggerItem key={c.case_id} className="case-row">
            <span className="case-row-id">
              <Hash value={c.case_id} length={8} />
            </span>
            <span className="case-row-date">
              {known?.reference ? <strong className="case-row-ref">{known.reference}</strong> : null}
              {utc(c.created_utc)}
            </span>
            <span className={`state state-${c.state}`}>{STATE_TEXT[c.state]}</span>
            <Button
              onClick={() => {
                onUnlock(c.case_id);
              }}
              busy={busy === c.case_id}
              disabled={c.state !== "active"}
            >
              Unlock...
            </Button>
            {known ? <Details details={known} /> : null}
          </StaggerItem>
        );
      })}
    </StaggerList>
  );
}
