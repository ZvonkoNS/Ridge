// "Device-secret recovery" (ADR-012): export this account's OS-keystore secret sealed under a
// separate recovery passphrase, or restore it into an account that has lost it. The Rust core
// opens the dialogs and both passphrase prompts; this card only sees the key id, the secret's
// fingerprint and the file.
import { useState } from "react";

import { Button, Notice } from "../components/ui";
import { IpcError, ipc } from "../ipc/commands";

export function RecoveryCard() {
  const [busy, setBusy] = useState<"export" | "import" | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const run = async (kind: "export" | "import") => {
    setBusy(kind);
    setDone(null);
    setProblem(null);
    try {
      if (kind === "export") {
        const made = await ipc.exportRecovery();
        setDone(
          `Recovery file for key ${made.key_id} (secret ${made.fingerprint}) saved. Keep it apart from the recovery passphrase, for example in a sealed envelope in the laboratory safe.`,
        );
      } else {
        const restored = await ipc.importRecovery();
        setDone(
          `Device secret ${restored.fingerprint} restored into this account. Your cases open again with your examiner passphrase.`,
        );
      }
    } catch (error) {
      if (!(error instanceof IpcError && error.kind === "cancelled")) {
        setProblem(error instanceof Error ? error.message : "The recovery file could not be used.");
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card" aria-labelledby="recovery-title">
      <h2 id="recovery-title">Device-secret recovery</h2>
      <p>
        Your cases need your examiner passphrase and a secret in this account&apos;s OS keystore. Backups do
        not hold that secret. A recovery file seals it under a separate recovery passphrase, so the laboratory
        can restore your cases on a new account. It holds no evidence. Each export and restore is recorded in
        the store audit file.
      </p>
      <div className="store-actions">
        <Button onClick={() => void run("export")} busy={busy === "export"}>
          Export recovery file...
        </Button>
        <Button onClick={() => void run("import")} busy={busy === "import"}>
          Restore from a recovery file...
        </Button>
      </div>
      {done ? <Notice tone="ok">{done}</Notice> : null}
      {problem ? <Notice tone="error">{problem}</Notice> : null}
    </section>
  );
}
