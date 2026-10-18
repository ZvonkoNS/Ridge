// The custody log as a readable timeline, newest first: what happened to the case, when and by
// whom. The sidecar verified the hash chain when the case was opened; this view only reads it.
import { useEffect, useState } from "react";

import { Button, Hash, utc } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { CustodyEntry } from "../ipc/types";

const PAGE = 100;

const FILTERS: [string, string][] = [
  ["", "All entries"],
  ["evidence", "Evidence"],
  ["job", "Jobs"],
  ["report", "Reports"],
  ["examiner", "Notes"],
  ["case", "Case (hold, verify)"],
  ["chain", "Signed heads"],
];

/** The fields worth a glance, in plain words; the full entry is in the processing record. */
export function entryDetails(entry: CustodyEntry): string {
  const parts: string[] = [];
  const text = (key: string): string | null => {
    const value = entry[key];
    return typeof value === "string" ? value : null;
  };
  const label = text("label");
  if (label) parts.push(label);
  const source = text("source");
  if (source) parts.push(`source: ${source}`);
  const note = text("text");
  if (note) parts.push(`“${note.length > 160 ? `${note.slice(0, 157)}...` : note}”`);
  const reason = text("reason");
  if (reason) parts.push(`reason: ${reason}`);
  if (typeof entry.legal_hold === "boolean") parts.push(entry.legal_hold ? "hold placed" : "hold lifted");
  const destination = text("destination");
  if (destination) parts.push(`to ${destination}`);
  const error = text("error");
  if (error) parts.push(`error: ${error}`);
  return parts.join(" · ");
}

export function CustodyLog({
  refresh,
  onFailure,
}: {
  refresh?: unknown;
  onFailure: (error: unknown) => void;
}) {
  const [filter, setFilter] = useState("");
  const [entries, setEntries] = useState<CustodyEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    ipc.custodyLog(0, PAGE, filter || null).then((page) => {
      setEntries(page.entries);
      setTotal(page.total);
    }, onFailure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, refresh]);

  const more = async () => {
    setBusy(true);
    try {
      const page = await ipc.custodyLog(entries?.length ?? 0, PAGE, filter || null);
      setEntries([...(entries ?? []), ...page.entries]);
      setTotal(page.total);
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card card-wide" aria-labelledby="custody-title">
      <h2 id="custody-title">Custody log</h2>
      <p className="muted">
        Every action on this case, newest first. The chain of entries was verified when the case was opened.
      </p>
      <label className="field field-inline">
        <span>Show</span>
        <select
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
          }}
        >
          {FILTERS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {entries === null ? <p className="muted">Reading the custody log...</p> : null}
      {entries?.length === 0 ? <p className="empty">No entries of this kind.</p> : null}
      {entries && entries.length > 0 ? (
        <table className="custody-table">
          <caption className="visually-hidden">Custody log entries, newest first</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Time (UTC)</th>
              <th scope="col">Examiner</th>
              <th scope="col">Action</th>
              <th scope="col">Details</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.seq} className={e.result === "failed" ? "custody-failed" : undefined}>
                <td>{e.seq}</td>
                <td>{utc(e.ts_utc)}</td>
                <td>{e.actor}</td>
                <td>
                  <code>{e.action}</code>
                  {e.result === "failed" ? " (failed)" : ""}
                </td>
                <td>
                  {typeof e.job_id === "string" ? (
                    <>
                      job <Hash value={e.job_id} length={8} />{" "}
                    </>
                  ) : null}
                  {typeof e.sha256 === "string" ? (
                    <>
                      <Hash value={e.sha256} />{" "}
                    </>
                  ) : null}
                  {entryDetails(e)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {entries && entries.length < total ? (
        <Button onClick={() => void more()} busy={busy}>
          Show older entries ({total - entries.length} more)
        </Button>
      ) : null}
    </section>
  );
}
