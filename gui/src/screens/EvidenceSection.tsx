// Evidence photos of the case: import with a source note (FR-21), choose one to review.
import { useState } from "react";

import { Button, Hash, StaggerItem, StaggerList } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { Item } from "../ipc/types";
import { ReviewPanel } from "./ReviewPanel";

interface Props {
  items: Item[];
  onFailure: (error: unknown) => void;
  onChanged: () => void;
  notify: (message: string) => void;
}

function kib(size: number): string {
  return size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MiB` : `${Math.ceil(size / 1024)} KiB`;
}

export function EvidenceSection({ items, onFailure, onChanged, notify }: Props) {
  const evidence = items.filter((i) => i.role === "evidence");
  const [selected, setSelected] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [importing, setImporting] = useState(false);
  const chosen = evidence.find((i) => i.sha256 === selected) ?? null;

  const importPhoto = async () => {
    setImporting(true);
    try {
      const item = await ipc.importEvidence(source.trim() === "" ? null : source);
      notify(`Imported ${item.label}; SHA-256 ${item.sha256.slice(0, 12)} recorded in the custody log.`);
      setSource("");
      setSelected(item.sha256);
      onChanged();
    } catch (error) {
      onFailure(error);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="section section-evidence">
      <aside className="section-list">
        <h2>Evidence photos</h2>
        <form
          className="import"
          onSubmit={(e) => {
            e.preventDefault();
            void importPhoto();
          }}
        >
          <label className="field">
            <span>Source note (optional)</span>
            <input
              value={source}
              maxLength={200}
              placeholder="Exhibit 12, phone A"
              onChange={(e) => {
                setSource(e.target.value);
              }}
            />
          </label>
          <Button variant="primary" type="submit" busy={importing}>
            Import photo...
          </Button>
        </form>
        {evidence.length === 0 ? (
          <p className="empty">
            No evidence yet. Import a photo: Ridge hashes it, encrypts it and never changes it.
          </p>
        ) : (
          <StaggerList className="picklist" label="Evidence photos">
            {evidence.map((item) => (
              <StaggerItem key={item.sha256}>
                <button
                  type="button"
                  className={`pick${item.sha256 === selected ? " pick-on" : ""}`}
                  aria-pressed={item.sha256 === selected}
                  onClick={() => {
                    setSelected(item.sha256);
                  }}
                >
                  <span className="pick-title">{item.label}</span>
                  {item.source ? <span className="pick-sub">{item.source}</span> : null}
                  <span className="pick-meta">
                    <Hash value={item.sha256} length={10} /> · {kib(item.size)}
                  </span>
                </button>
              </StaggerItem>
            ))}
          </StaggerList>
        )}
      </aside>
      <div className="section-main">
        {chosen ? (
          <ReviewPanel
            key={chosen.sha256}
            evidence={chosen}
            allEvidence={evidence}
            onFailure={onFailure}
            onJobDone={onChanged}
            notify={notify}
          />
        ) : (
          <p className="empty empty-main">Choose an evidence photo to review it and run extraction jobs.</p>
        )}
      </div>
    </div>
  );
}
