// "Check exported files": verify a report, processing record, custody head, key card, key register,
// limits file, disclosure package or store backup without a case store (for the FQM, the DPO, IT or
// a reviewer).
// The Rust core opens the dialogs and the sidecar runs the same verifiers as the CLI.
import { useId, useState } from "react";

import { Button, Notice } from "../components/ui";
import { IpcError, ipc } from "../ipc/commands";
import type { FileCheck } from "../ipc/types";

export function CheckFiles() {
  const registerId = useId();
  const [withRegister, setWithRegister] = useState(false);
  const [busy, setBusy] = useState<"file" | "folder" | null>(null);
  const [result, setResult] = useState<FileCheck | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const check = async (folder: boolean) => {
    setBusy(folder ? "folder" : "file");
    setProblem(null);
    setResult(null);
    try {
      setResult(await ipc.checkExported(folder, withRegister));
    } catch (error) {
      if (!(error instanceof IpcError && error.kind === "cancelled")) {
        setProblem(error instanceof Error ? error.message : "The file could not be checked.");
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card" aria-labelledby="check-files-title">
      <h2 id="check-files-title">Check exported files</h2>
      <p>
        Verify a signed report, processing record, custody head, key card, key register, limits file,
        disclosure package or store backup. No case store is needed and nothing is changed.
      </p>
      <label className="check" htmlFor={registerId}>
        <input
          id={registerId}
          type="checkbox"
          checked={withRegister}
          onChange={(e) => {
            setWithRegister(e.target.checked);
          }}
        />{" "}
        Name the signer from the laboratory&apos;s key register
      </label>
      <div className="store-actions">
        <Button onClick={() => void check(false)} busy={busy === "file"}>
          Check a file...
        </Button>
        <Button onClick={() => void check(true)} busy={busy === "folder"}>
          Check a package or backup folder...
        </Button>
      </div>
      {result ? (
        <Notice tone="ok">
          <strong>{result.title}: verified.</strong>
          <ul className="limits-warnings">
            {result.details.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Notice>
      ) : null}
      {problem ? <Notice tone="error">Not verified: {problem}</Notice> : null}
    </section>
  );
}
