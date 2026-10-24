// Evidence photos of the case: import with a source note (FR-21), choose one to review.
import { useState } from "react";

import { CaptureCheckCard } from "../components/CaptureCheckCard";
import { NotesPanel } from "../components/NotesPanel";
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
      const batch = await ipc.importEvidence(source.trim() === "" ? null : source);
      const last = batch.imported.at(-1);
      if (last) {
        setSource("");
        setSelected(last.sha256);
        onChanged();
      }
      const done =
        batch.imported.length === 1 && last
          ? `Imported ${last.label}; SHA-256 ${last.sha256.slice(0, 12)} recorded in the custody log.`
          : `Imported ${batch.imported.length} photos; each SHA-256 is recorded in the custody log.`;
      if (batch.refused.length > 0) {
        const refused = batch.refused.map((r) => `${r.name}: ${r.message}`).join("; ");
        onFailure(new Error(`${batch.imported.length > 0 ? `${done} ` : ""}Not imported: ${refused}.`));
      } else {
        notify(done);
      }
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
            Import photos...
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
          <>
            <ReviewPanel
              key={chosen.sha256}
              evidence={chosen}
              allEvidence={evidence}
              onFailure={onFailure}
              onJobDone={onChanged}
              notify={notify}
            />
            <NotesPanel
              key={`notes-${chosen.sha256}`}
              jobId={null}
              sha256={chosen.sha256}
              onFailure={onFailure}
            />
            <CaptureCheckCard key={`check-${chosen.sha256}`} sha256={chosen.sha256} onFailure={onFailure} />
          </>
        ) : (
          <div className="empty-main">
            <p className="empty">Choose an evidence photo to review it and run extraction jobs.</p>
            <CaptureCheckCard sha256={null} onFailure={onFailure} />
          </div>
        )}
      </div>
    </div>
  );
}
