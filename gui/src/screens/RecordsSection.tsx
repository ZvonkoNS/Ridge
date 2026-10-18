// Integrity and records: verify the case (FR-24), export the signed processing record (PRIV-3),
// place or lift a legal hold (FR-26). Disposal stays in the CLI (`ridge-case dispose`), with its
// typed confirmation, on purpose. Examiner notes of the whole case are listed here too.
import { useEffect, useState } from "react";

import { NotesPanel } from "../components/NotesPanel";
import { Button, Notice, utc } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { CaseInfo, CustodyEntry, Item, LimitsStatus, Verification } from "../ipc/types";
import { CaseSummary } from "./CaseSummary";
import { CustodyLog } from "./CustodyLog";
import { Inventory, LimitsCard } from "./Inventory";

interface Props {
  info: CaseInfo | null;
  items: Item[];
  limits: LimitsStatus | null;
  onInfo: (info: CaseInfo) => void;
  onFailure: (error: unknown) => void;
  notify: (message: string) => void;
}

type Action = "verify" | "log" | "hold" | "head" | "package";

/** When the case was last verified, from the custody log (a check by any Ridge window counts). */
function LastVerified({ refresh, onFailure }: { refresh: unknown; onFailure: (error: unknown) => void }) {
  const [last, setLast] = useState<CustodyEntry | null | undefined>(undefined);
  useEffect(() => {
    ipc.custodyLog(0, 1, "case.verify").then((page) => {
      setLast(page.entries[0] ?? null);
    }, onFailure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);
  if (last === undefined) {
    return null;
  }
  if (last === null) {
    return <p className="muted">This case has not been verified yet.</p>;
  }
  const problems = typeof last.problems === "number" ? last.problems : 0;
  return (
    <p className="muted">
      Last verified {utc(last.ts_utc)} by {last.actor}:{" "}
      {last.result === "ok" ? "passed" : `FAILED with ${problems} problem(s)`}.
    </p>
  );
}

export function RecordsSection({ info, items, limits, onInfo, onFailure, notify }: Props) {
  const [verification, setVerification] = useState<Verification | null>(null);
  const [busy, setBusy] = useState<Action | null>(null);
  const [reason, setReason] = useState("");

  // Every logged action changes the custody log: the summary, last-verified line and log view reload.
  const [changes, setChanges] = useState(0);
  const changed = () => {
    setChanges((n) => n + 1);
  };

  const run = async (what: Action) => {
    setBusy(what);
    try {
      if (what === "verify") {
        setVerification(await ipc.verifyCase());
      } else if (what === "package") {
        const done = await ipc.exportPackage();
        notify(
          `Disclosure package written: the processing record and ${done.reports} signed report(s), signed with key ${done.key_id}.`,
        );
      } else if (what === "head") {
        const done = await ipc.exportHead();
        notify(`Custody head at entry ${done.seq} exported for countersigning (key ${done.key_id}).`);
      } else if (what === "log") {
        const done = await ipc.exportLog();
        notify(`Processing record exported: ${done.entries} signed custody entries, key ${done.key_id}.`);
      } else if (info) {
        const next = await ipc.setLegalHold(!info.legal_hold, reason);
        onInfo(next);
        setReason("");
        notify(
          next.legal_hold ? "Legal hold placed; disposal is refused while it lasts." : "Legal hold lifted.",
        );
      }
      changed();
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="section section-wide records">
      <CaseSummary refresh={changes} onFailure={onFailure} />
      <section className="card" aria-labelledby="verify-title">
        <h2 id="verify-title">Verify the case</h2>
        <p>
          Checks the hash of every stored item, the custody chain and every signature, and reports the first
          problem precisely.
        </p>
        <LastVerified refresh={changes} onFailure={onFailure} />
        <Button variant="primary" onClick={() => void run("verify")} busy={busy === "verify"}>
          Verify now
        </Button>
        {verification ? (
          verification.ok ? (
            <Notice tone="ok">
              Verification passed: {verification.items} items and {verification.reports} signed reports
              checked.
            </Notice>
          ) : (
            <Notice tone="error">
              Verification FAILED with {verification.problems.length} problem(s):
              <ul>
                {verification.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </Notice>
          )
        ) : null}
      </section>
      <section className="card" aria-labelledby="log-title">
        <h2 id="log-title">Processing record</h2>
        <p>
          Exports every custody entry with a signed chain head, readable without the case store, for the data
          protection officer. <code>ridge-case check-log</code> verifies it offline.
        </p>
        <Button onClick={() => void run("log")} busy={busy === "log"}>
          Export processing record...
        </Button>
      </section>
      <section className="card" aria-labelledby="package-title">
        <h2 id="package-title">Disclosure package</h2>
        <p>
          Writes the signed processing record and every signed job report to a new folder, with a manifest
          signed by your key. It contains no images: the reports name the SHA-256 of every image, so exported
          images can be matched to them. <code>ridge-case check-package</code> verifies the folder offline.
        </p>
        <Button onClick={() => void run("package")} busy={busy === "package"}>
          Export disclosure package...
        </Button>
      </section>
      <section className="card" aria-labelledby="head-title">
        <h2 id="head-title">Custody head for countersigning</h2>
        <p>
          Exports the current signed head of the custody log as a small file for the laboratory to countersign
          or timestamp. A later processing record can then be checked against it (
          <code>ridge-case check-head head.json --record record.json</code>), which shows whether entries were
          removed or rewritten after the head.
        </p>
        <Button onClick={() => void run("head")} busy={busy === "head"}>
          Export custody head...
        </Button>
      </section>
      <section className="card" aria-labelledby="hold-title">
        <h2 id="hold-title">Legal hold</h2>
        <p>
          {info?.legal_hold
            ? "This case is on legal hold. It cannot be disposed of."
            : "No legal hold. The case may be disposed of after its retention date."}
        </p>
        <form
          className="import"
          onSubmit={(e) => {
            e.preventDefault();
            void run("hold");
          }}
        >
          <label className="field">
            <span>Reason (recorded in the custody log)</span>
            <input
              value={reason}
              required
              maxLength={500}
              placeholder="Court order 12/2026"
              onChange={(e) => {
                setReason(e.target.value);
              }}
            />
          </label>
          <Button
            type="submit"
            variant={info?.legal_hold ? "quiet" : "danger"}
            busy={busy === "hold"}
            disabled={!info || reason.trim() === ""}
          >
            {info?.legal_hold ? "Lift legal hold" : "Place legal hold"}
          </Button>
        </form>
      </section>
      <div className="card">
        <NotesPanel jobId={null} onFailure={onFailure} level={2} onAdded={changed} />
      </div>
      <LimitsCard limits={limits} />
      <Inventory items={items} limits={limits} onFailure={onFailure} notify={notify} onExported={changed} />
      <CustodyLog refresh={changes} onFailure={onFailure} />
    </div>
  );
}
