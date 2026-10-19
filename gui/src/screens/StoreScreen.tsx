// Choose a case store, create the examiner identity on first run, create or unlock a case.
// Passphrases are never typed here: the Rust core opens its own prompt window (ADR-010).
import { useState } from "react";

import { AboutRidge } from "../components/AboutRidge";
import { CopyButton } from "../components/CopyButton";
import { Button, Hash, Notice } from "../components/ui";
import { IpcError, ipc } from "../ipc/commands";
import type { CaseOverview, SessionInfo, StoreCheck, StoreView } from "../ipc/types";
import { CheckFiles } from "./CheckFiles";
import { RecoveryCard } from "./RecoveryCard";
import { type NewCase, NewCaseForm } from "./NewCaseForm";
import { WorkstationCheck } from "./WorkstationCheck";
import { CaseList, StoreChecks, findCases } from "./StoreCases";

interface Props {
  store: StoreView | null;
  notice: string | null;
  engineProblem?: string | null;
  versions?: string | null;
  onStore: (store: StoreView) => void;
  onOpened: (session: SessionInfo) => void;
}

function message(error: unknown): string | null {
  if (error instanceof IpcError && error.kind === "cancelled") {
    return null;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

// The Rust core asks for a reinstall when the engine file is missing: restarting would not help.
function engineAdvice(problem: string): string {
  return problem.includes("reinstall Ridge")
    ? "If this persists after reinstalling, report it."
    : "Restart Ridge; if this persists, report it.";
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
  // Results belong to the store they were read from; choosing another store hides them.
  const [checked, setChecked] = useState<{ path: string; checks: StoreCheck[] } | null>(null);
  const checks = checked?.path === store?.path ? (checked?.checks ?? null) : null;
  const [query, setQuery] = useState("");
  const [holder, setHolder] = useState("");
  const [cardNote, setCardNote] = useState<string | null>(null);
  const [backupNote, setBackupNote] = useState<string | null>(null);
  const [onlyDue, setOnlyDue] = useState(false);
  const [about, setAbout] = useState(false);
  // Details belong to the store they were read from; choosing another store hides them.
  const [overview, setOverview] = useState<{ path: string; cases: Map<string, CaseOverview> } | null>(null);
  const details = overview?.path === store?.path ? (overview?.cases ?? null) : null;
  const shown = store
    ? findCases(store.cases, details, query).filter((c) => !onlyDue || details?.get(c.case_id)?.due === true)
    : [];

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
  const verifyAll = () =>
    attempt("verify", async () => {
      const path = store?.path ?? "";
      setChecked({ path, checks: await ipc.verifyStore() });
      onStore(await ipc.refreshStore());
    });
  const showDetails = () =>
    attempt("details", async () => {
      const path = store?.path ?? "";
      const cases = await ipc.storeOverview();
      setOverview({ path, cases: new Map(cases.map((c) => [c.case_id, c])) });
    });
  const backup = () =>
    attempt("backup", async () => {
      const done = await ipc.backupStore();
      setCardNote(null);
      setBackupNote(
        `Backup written: ${String(done.files)} encrypted file(s) with a hash manifest. It does not hold the OS-keystore secret that unlocking also needs.`,
      );
    });
  const exportCard = () =>
    attempt("card", async () => {
      const card = await ipc.exportKeyCard(holder);
      setCardNote(
        `Key card for key ${card.key_id} saved. Give it to the laboratory, which confirms who you are before registering it.`,
      );
    });
  const create = (form: NewCase) =>
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
          The processing engine is not available: {engineProblem}. {engineAdvice(engineProblem)}
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
        <div className="store-actions">
          <Button
            variant={store ? "quiet" : "primary"}
            onClick={() => void choose()}
            busy={busy === "choose"}
          >
            {store ? "Choose another store..." : "Choose case store..."}
          </Button>
          {store?.identity.exists ? (
            <Button onClick={() => void backup()} busy={busy === "backup"}>
              Back up this store...
            </Button>
          ) : null}
        </div>
        {backupNote ? <Notice tone="ok">{backupNote}</Notice> : null}
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
              Signing key <Hash value={store.identity.key_id} length={16} />{" "}
              <CopyButton value={store.identity.key_id} what="signing key id" />
            </p>
            <details className="key-card">
              <summary>Register this key with the laboratory</summary>
              <form
                className="import"
                onSubmit={(e) => {
                  e.preventDefault();
                  void exportCard();
                }}
              >
                <label className="field">
                  <span>Your name as the laboratory registers it</span>
                  <input
                    required
                    maxLength={200}
                    value={holder}
                    onChange={(e) => {
                      setHolder(e.target.value);
                    }}
                  />
                </label>
                <Button type="submit" busy={busy === "card"} disabled={holder.trim() === ""}>
                  Export key card...
                </Button>
              </form>
              {cardNote ? <Notice tone="ok">{cardNote}</Notice> : null}
            </details>
            {store.cases.length === 0 ? <p className="empty">No cases in this store yet.</p> : null}
            {store.cases.length > 1 ? (
              <label className="field case-find">
                <span>
                  {details
                    ? "Find a case by reference or id"
                    : "Find a case by id (show details to search references)"}
                </span>
                <input
                  type="search"
                  value={query}
                  maxLength={200}
                  onChange={(e) => {
                    setQuery(e.target.value);
                  }}
                />
              </label>
            ) : null}
            {details ? (
              <label className="check">
                <input
                  type="checkbox"
                  checked={onlyDue}
                  onChange={(e) => {
                    setOnlyDue(e.target.checked);
                  }}
                />{" "}
                Only cases past their retention date without a legal hold
              </label>
            ) : null}
            {(query || onlyDue) && shown.length === 0 ? (
              <p className="empty">
                {onlyDue && !query ? "No case is past its retention date." : `No case matches “${query}”.`}
              </p>
            ) : null}
            <CaseList
              cases={shown}
              details={details}
              busy={busy}
              onUnlock={(caseId) => void unlock(caseId)}
            />
            {store.cases.length > 0 ? (
              <div className="store-actions">
                {details ? null : (
                  <Button onClick={() => void showDetails()} busy={busy === "details"}>
                    Show case details...
                  </Button>
                )}
                <Button onClick={() => void verifyAll()} busy={busy === "verify"}>
                  Verify all cases...
                </Button>
              </div>
            ) : null}
            {checks ? <StoreChecks checks={checks} /> : null}
          </section>
          <NewCaseForm busy={busy === "create"} onCreate={(form) => void create(form)} />
        </>
      ) : null}
      {store?.identity.exists ? <RecoveryCard /> : null}
      <CheckFiles />
      {/* keyed by store: findings belong to the store they were read from */}
      {store ? <WorkstationCheck key={store.path} /> : null}
      {versions ? <p className="versions">{versions}</p> : null}
      <p className="versions">
        <button
          type="button"
          className="link-button"
          onClick={() => {
            setAbout(true);
          }}
        >
          About Ridge
        </button>
      </p>
      {about ? (
        <AboutRidge
          versions={versions}
          storePath={store?.path ?? null}
          onClose={() => {
            setAbout(false);
          }}
        />
      ) : null}
    </main>
  );
}
