// Choose a case store, create the examiner identity on first run, create or unlock a case.
// Passphrases are never typed here: the Rust core opens its own prompt window (ADR-010).
import { useState } from "react";

import { Button, Hash, Notice, StaggerItem, StaggerList, utc } from "../components/ui";
import { IpcError, ipc } from "../ipc/commands";
import type { CaseSummary, SessionInfo, StoreView } from "../ipc/types";

interface Props {
  store: StoreView | null;
  notice: string | null;
  engineProblem?: string | null;
  versions?: string | null;
  onStore: (store: StoreView) => void;
  onOpened: (session: SessionInfo) => void;
}

const STATE_TEXT: Record<CaseSummary["state"], string> = {
  active: "ready",
  locked: "open in another Ridge window",
  erasing: "disposal interrupted",
  disposed: "disposed",
  invalid: "unreadable",
};

function message(error: unknown): string | null {
  if (error instanceof IpcError && error.kind === "cancelled") {
    return null;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function StoreScreen({
  store,
  notice,
  engineProblem = null,
  versions = null,
  onStore,
  onOpened,
}: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [form, setForm] = useState({ reference: "", legalBasis: "", retention: "" });

  const attempt = async (key: string, work: () => Promise<void>) => {
    setBusy(key);
    setProblem(null);
    try {
      await work();
    } catch (error) {
      setProblem(message(error));
    } finally {
      setBusy(null);
    }
  };

  const choose = () =>
    attempt("choose", async () => {
      onStore(await ipc.chooseStore());
    });
  const createIdentity = () =>
    attempt("identity", async () => {
      await ipc.createIdentity();
      onStore(await ipc.refreshStore());
    });
  const unlock = (caseId: string) =>
    attempt(caseId, async () => {
      onOpened(await ipc.unlockCase(caseId));
    });
  const create = () =>
    attempt("create", async () => {
      const created = await ipc.createCase(form.reference, form.legalBasis, form.retention);
      onStore(await ipc.refreshStore());
      if (created.session) {
        onOpened(created.session);
      }
    });

  return (
    <main className="start" id="main">
      <header className="start-head">
        <h1 className="wordmark">Ridge</h1>
        <p className="start-lede">
          Fingerprint image enhancement for examiners. Offline, encrypted, every step logged and signed.
        </p>
      </header>
      {engineProblem ? (
        <Notice tone="error">
          The processing engine is not available: {engineProblem}. Restart Ridge; if this persists, report it.
        </Notice>
      ) : null}
      {notice ? <Notice tone="info">{notice}</Notice> : null}
      {problem ? (
        <Notice
          tone="error"
          onDismiss={() => {
            setProblem(null);
          }}
        >
          {problem}
        </Notice>
      ) : null}
      <section className="card store-card" aria-labelledby="store-title">
        <h2 id="store-title">Case store</h2>
        {store ? (
          <p className="path">{store.path}</p>
        ) : (
          <p>Choose the folder that holds your encrypted cases, or an empty folder to start one.</p>
        )}
        <Button variant={store ? "quiet" : "primary"} onClick={() => void choose()} busy={busy === "choose"}>
          {store ? "Choose another store..." : "Choose case store..."}
        </Button>
      </section>
      {store && !store.identity.exists ? (
        <section className="card" aria-labelledby="identity-title">
          <h2 id="identity-title">First run: your examiner identity</h2>
          <p>
            Ridge signs every report and custody record with a key that only your passphrase and this OS
            account can unlock. Register the key id it shows with your lab.
          </p>
          <Button variant="primary" onClick={() => void createIdentity()} busy={busy === "identity"}>
            Create examiner identity...
          </Button>
        </section>
      ) : null}
      {store?.identity.exists ? (
        <>
          <section className="card" aria-labelledby="cases-title">
            <h2 id="cases-title">Cases</h2>
            <p className="muted">
              Signing key <Hash value={store.identity.key_id} length={16} />
            </p>
            {store.cases.length === 0 ? <p className="empty">No cases in this store yet.</p> : null}
            <StaggerList className="caselist" label="Cases">
              {store.cases.map((c) => (
                <StaggerItem key={c.case_id} className="case-row">
                  <span className="case-row-id">
                    <Hash value={c.case_id} length={8} />
                  </span>
                  <span className="case-row-date">{utc(c.created_utc)}</span>
                  <span className={`state state-${c.state}`}>{STATE_TEXT[c.state]}</span>
                  <Button
                    onClick={() => void unlock(c.case_id)}
                    busy={busy === c.case_id}
                    disabled={c.state !== "active"}
                  >
                    Unlock...
                  </Button>
                </StaggerItem>
              ))}
            </StaggerList>
          </section>
          <section className="card" aria-labelledby="new-title">
            <h2 id="new-title">New case</h2>
            <form
              className="newcase"
              onSubmit={(e) => {
                e.preventDefault();
                void create();
              }}
            >
              <label className="field">
                <span>Case reference</span>
                <input
                  required
                  maxLength={200}
                  value={form.reference}
                  placeholder="KT-2026-0001"
                  onChange={(e) => {
                    setForm({ ...form, reference: e.target.value });
                  }}
                />
              </label>
              <label className="field">
                <span>Legal basis</span>
                <input
                  required
                  maxLength={500}
                  value={form.legalBasis}
                  placeholder="Order or article"
                  onChange={(e) => {
                    setForm({ ...form, legalBasis: e.target.value });
                  }}
                />
              </label>
              <label className="field">
                <span>Keep until (retention date)</span>
                <input
                  required
                  type="date"
                  value={form.retention}
                  onChange={(e) => {
                    setForm({ ...form, retention: e.target.value });
                  }}
                />
              </label>
              <Button variant="primary" type="submit" busy={busy === "create"}>
                Create case...
              </Button>
            </form>
          </section>
        </>
      ) : null}
      {versions ? <p className="versions">{versions}</p> : null}
    </main>
  );
}
