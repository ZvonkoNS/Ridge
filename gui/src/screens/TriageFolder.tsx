// "Which photos first?" (FR-57): the capture check on every photo of a folder chosen in a native
// dialog, listed with a measurable ridge pattern first. Read-only; the index, when asked for, is a
// new CSV file chosen in a save dialog. A reading order for the examiner, who still looks at every
// photo: never a quality judgement of a print, never a selection.
import { useId, useState } from "react";

import { Button, Notice } from "../components/ui";
import { IpcError, ipc } from "../ipc/commands";
import type { Triage, TriageGroup, TriageRow } from "../ipc/types";

/** The groups in reading order, as the sidecar sorts them. */
export const GROUP_ORDER: TriageGroup[] = [
  "finger-ridges",
  "ridges-no-finger",
  "finger-unclear",
  "nothing",
  "refused",
];

/** What was measured on a row (its clarity), or why the file was not read. */
export function rowDetail(row: TriageRow): string {
  if (row.check === null) {
    return row.reason;
  }
  return row.check.clarity === null ? "clarity not measured" : `clarity ${row.check.clarity.toFixed(3)}`;
}

function heading(triage: Triage): string {
  let text = `${triage.photos} photo(s) checked in ${triage.folder}`;
  if (triage.recursive) {
    text += ", subfolders included";
  }
  if (triage.other_files > 0) {
    text += `, ${triage.other_files} other file(s) not read`;
  }
  return text;
}

function TriageResult({ triage }: { triage: Triage }) {
  return (
    <div className="triage-result" aria-live="polite">
      <p>
        <strong>{heading(triage)}</strong>
      </p>
      <ul className="findings">
        {GROUP_ORDER.filter((group) => triage.counts[group] > 0).map((group) => (
          <li key={group}>
            <span className="badge">{group}</span> {triage.counts[group]}: {triage.groups[group]}
          </li>
        ))}
      </ul>
      {triage.index ? (
        <p className="muted">
          Index saved to {triage.index.path} (SHA-256 <code>{triage.index.sha256}</code>)
        </p>
      ) : null}
      <div className="triage-rows">
        <table className="inventory">
          <caption className="visually-hidden">Every file of the folder in reading order</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Group</th>
              <th scope="col">Measured</th>
              <th scope="col">File</th>
            </tr>
          </thead>
          <tbody>
            {triage.rows.map((row) => (
              <tr key={row.order}>
                <td>{row.order}</td>
                <td>{row.group}</td>
                <td>{rowDetail(row)}</td>
                <td>{row.file}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">{triage.notice}</p>
    </div>
  );
}

/** The store-screen card: options, the button that opens the folder dialog, and the reading order. */
export function TriageFolder() {
  const recursiveId = useId();
  const saveId = useId();
  const [recursive, setRecursive] = useState(false);
  const [saveIndex, setSaveIndex] = useState(false);
  const [busy, setBusy] = useState(false);
  const [triage, setTriage] = useState<Triage | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setProblem(null);
    setTriage(null);
    try {
      setTriage(await ipc.triageFolder(recursive, saveIndex));
    } catch (error) {
      if (!(error instanceof IpcError && error.kind === "cancelled")) {
        setProblem(error instanceof Error ? error.message : "The folder could not be checked.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card card-wide" aria-labelledby="triage-title">
      <h2 id="triage-title">Which photos first?</h2>
      <p>
        Runs the capture check on every photo of a folder, each read once and never changed, and lists them
        with a located finger and a clear ridge wave first. A reading order for you, who still looks at every
        photo: not a quality judgement of any print, and nothing is moved, selected or submitted. A few
        seconds per photo; up to 300 photos here (the command line takes more).
      </p>
      <label className="check" htmlFor={recursiveId}>
        <input
          id={recursiveId}
          type="checkbox"
          checked={recursive}
          onChange={(e) => {
            setRecursive(e.target.checked);
          }}
        />{" "}
        Include subfolders
      </label>
      <label className="check" htmlFor={saveId}>
        <input
          id={saveId}
          type="checkbox"
          checked={saveIndex}
          onChange={(e) => {
            setSaveIndex(e.target.checked);
          }}
        />{" "}
        Also save the index as a CSV file (outside the folder, never replacing one)
      </label>
      <div className="store-actions">
        <Button
          onClick={() => {
            void run();
          }}
          busy={busy}
        >
          Check a folder of photos...
        </Button>
      </div>
      {busy ? (
        <p className="muted" role="status">
          Checking the photos: a few seconds each.
        </p>
      ) : null}
      {problem ? <Notice tone="error">{problem}</Notice> : null}
      {triage ? <TriageResult triage={triage} /> : null}
    </section>
  );
}
