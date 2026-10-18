// Integrity and records: verify the case (FR-24), export the signed processing record (PRIV-3),
// place or lift a legal hold (FR-26). Disposal stays in the CLI (`ridge-case dispose`), with its
// typed confirmation, on purpose.
import { useState } from "react";

import { Button, Notice } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { CaseInfo, Item, LimitsStatus, Verification } from "../ipc/types";
import { Inventory, LimitsCard } from "./Inventory";

interface Props {
  info: CaseInfo | null;
  items: Item[];
  limits: LimitsStatus | null;
  onInfo: (info: CaseInfo) => void;
  onFailure: (error: unknown) => void;
  notify: (message: string) => void;
}

export function RecordsSection({ info, items, limits, onInfo, onFailure, notify }: Props) {
  const [verification, setVerification] = useState<Verification | null>(null);
  const [busy, setBusy] = useState<"verify" | "log" | "hold" | null>(null);
  const [reason, setReason] = useState("");

  const run = async (what: "verify" | "log" | "hold") => {
    setBusy(what);
    try {
      if (what === "verify") {
        setVerification(await ipc.verifyCase());
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
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="section section-wide records">
      <section className="card" aria-labelledby="verify-title">
        <h2 id="verify-title">Verify the case</h2>
        <p>
          Checks the hash of every stored item, the custody chain and every signature, and reports the first
          problem precisely.
        </p>
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
      <LimitsCard limits={limits} />
      <Inventory items={items} limits={limits} onFailure={onFailure} notify={notify} />
    </div>
  );
}
