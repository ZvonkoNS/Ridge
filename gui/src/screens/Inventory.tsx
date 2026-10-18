// Everything stored in the case, as the custody log records it, with a logged export for any item
// (FR-25): originals, references, prints, exports, debug images and minutiae JSON.
import { useState } from "react";

import { CopyButton } from "../components/CopyButton";
import { roleName } from "../components/ExhibitLabel";
import { Button, Hash } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { Item, LimitsStatus } from "../ipc/types";

interface Props {
  items: Item[];
  limits: LimitsStatus | null;
  onFailure: (error: unknown) => void;
  notify: (message: string) => void;
  /** Told after each export (it is logged), so custody views can reload. */
  onExported?: () => void;
}

function size(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MiB` : `${Math.ceil(bytes / 1024)} KiB`;
}

export function LimitsCard({ limits }: { limits: LimitsStatus | null }) {
  return (
    <section className="card" aria-labelledby="limits-title">
      <h2 id="limits-title">Limits of use</h2>
      {limits === null ? <p className="muted">Reading the store...</p> : null}
      {limits && !limits.configured ? (
        <p>
          No limits of use are configured for this store. When the laboratory&apos;s validation sets them (
          <code>limits-of-use.json</code> in the store), every job report records whether the job stayed
          within them.
        </p>
      ) : null}
      {limits?.configured ? (
        <>
          <p>
            From <strong>{limits.source}</strong> · <abbr title="SHA-256">sha256</abbr>{" "}
            <Hash value={limits.sha256} />
          </p>
          {limits.signed_by ? (
            <p>
              Signed with key <Hash value={limits.signed_by.key_id} length={16} />. Confirm with the
              laboratory that this is the Forensic Quality Manager&apos;s key.
            </p>
          ) : (
            <p className="muted">
              Not signed. The Forensic Quality Manager can sign the file with{" "}
              <code>ridge-case limits --sign</code>; reports then name the signing key.
            </p>
          )}
          <ul className="paramlist">
            {Object.entries(limits.limits).map(([key, value]) => (
              <li key={key}>
                <span className="paramlist-key">{key}</span>{" "}
                <code>{Array.isArray(value) ? value.join(", ") : String(value)}</code>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

export function Inventory({ items, onFailure, notify, onExported }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const exportOne = async (item: Item) => {
    setBusy(item.sha256);
    try {
      const done = await ipc.exportItem(item.sha256, item.label);
      notify(
        `Exported ${item.label} (${done.exported.split(/[\\/]/).pop() ?? ""}); the export is in the custody log.`,
      );
      onExported?.();
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };
  const exportAll = async (role: string) => {
    setBusy(`all-${role}`);
    try {
      const done = await ipc.exportAll(role);
      notify(
        `${String(done.files)} file(s) exported, listed in ${done.index}; each export is in the custody log.`,
      );
      onExported?.();
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };
  const exports = items.filter((i) => i.role === "export").length;
  const prints = items.filter((i) => i.role === "print").length;
  return (
    <section className="card card-wide" aria-labelledby="inventory-title">
      <h2 id="inventory-title">Stored items</h2>
      {exports > 1 || prints > 1 ? (
        <div className="store-actions">
          {exports > 1 ? (
            <Button onClick={() => void exportAll("export")} busy={busy === "all-export"}>
              Export all {exports} comparison exports...
            </Button>
          ) : null}
          {prints > 1 ? (
            <Button onClick={() => void exportAll("print")} busy={busy === "all-print"}>
              Export all {prints} processed prints...
            </Button>
          ) : null}
        </div>
      ) : null}
      <table className="inventory">
        <caption className="visually-hidden">Every item stored in the case</caption>
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col">Kind</th>
            <th scope="col">SHA-256</th>
            <th scope="col">Size</th>
            <th scope="col">
              <span className="visually-hidden">Action</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.sha256}>
              <td>
                {item.label}
                {item.source ? <small className="inventory-sub">{item.source}</small> : null}
              </td>
              <td>{roleName(item.role)}</td>
              <td>
                <Hash value={item.sha256} length={16} />{" "}
                <CopyButton value={item.sha256} what={`SHA-256 of ${item.label}`} />
              </td>
              <td>{size(item.size)}</td>
              <td>
                <Button
                  onClick={() => void exportOne(item)}
                  busy={busy === item.sha256}
                  aria-label={`Export ${item.label}`}
                >
                  Export...
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
