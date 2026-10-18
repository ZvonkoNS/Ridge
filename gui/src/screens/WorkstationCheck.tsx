// "This workstation": a read-only check of the installation, the OS keystore, the store and its
// limits of use, so the examiner or the laboratory sees what to fix before casework starts. Nothing
// is decrypted or logged; it does not validate the method or the installation.
import { useId, useState } from "react";

import { Button, Notice } from "../components/ui";
import { IpcError, ipc } from "../ipc/commands";
import type { WorkstationFinding } from "../ipc/types";

const LEVEL_TEXT: Record<WorkstationFinding["level"], string> = {
  ok: "OK",
  note: "Note",
  problem: "Problem",
};
const LEVEL_CLASS: Record<WorkstationFinding["level"], string> = {
  ok: "badge badge-ok",
  note: "badge badge-hold",
  problem: "badge badge-problem",
};

export function WorkstationCheck() {
  const registerId = useId();
  const [withRegister, setWithRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [found, setFound] = useState<WorkstationFinding[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const check = async () => {
    setBusy(true);
    setFailure(null);
    try {
      setFound(await ipc.workstationCheck(withRegister));
    } catch (error) {
      if (error instanceof IpcError && error.kind === "cancelled") {
        return; // the register dialog was closed: nothing was checked
      }
      setFound(null);
      setFailure(error instanceof Error ? error.message : "The workstation could not be checked.");
    } finally {
      setBusy(false);
    }
  };

  const problems = found?.filter((f) => f.level === "problem").length ?? 0;
  return (
    <section className="card" aria-labelledby="workstation-title">
      <h2 id="workstation-title">This workstation</h2>
      <p>
        Check the Ridge build, the OS keystore, this store and its limits of use. Nothing is decrypted,
        changed or logged.
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
        Also check this store&apos;s signing key in the laboratory&apos;s key register
      </label>
      <div className="store-actions">
        <Button onClick={() => void check()} busy={busy}>
          Check this workstation
        </Button>
      </div>
      {failure ? <Notice tone="error">{failure}</Notice> : null}
      {found ? (
        <>
          <p role="status">
            {problems === 0 ? "No problems found." : `${String(problems)} problem(s) to fix before casework.`}{" "}
            This checks the setup; it does not validate the method or the installation.
          </p>
          <ul className="findings">
            {found.map((f, i) => (
              <li key={`${f.topic}-${String(i)}`}>
                <span className={LEVEL_CLASS[f.level]}>{LEVEL_TEXT[f.level]}</span>{" "}
                <strong>{f.topic}:</strong> {f.text}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
