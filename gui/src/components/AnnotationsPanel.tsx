// Examiner annotations (FR-55): the sets of marks the examiner recorded on a job's output images,
// read from the custody log. Each set was signed when it was recorded; a newer set names the set it
// replaces. Marks are the examiner's statements, never a match or an identification.
import { useEffect, useState } from "react";

import { IpcError, ipc } from "../ipc/commands";
import type { Annotation } from "../ipc/types";
import { Button, Hash } from "./ui";

export const ANNOTATIONS_NOTE =
  "Marks are the examiner's own charting of an output image, recorded and signed in the custody log. They are not a match, a count of agreement or an identification.";

const KIND_WORD: Record<Annotation["marks"][number]["kind"], string> = {
  ending: "ending",
  bifurcation: "bifurcation",
  other: "other",
};

/** One line per set: when, by whom, on which image, how many marks of each kind. */
export function setLine(a: Annotation): string {
  const counts = a.marks.reduce<Record<string, number>>(
    (n, m) => ({ ...n, [m.kind]: (n[m.kind] ?? 0) + 1 }),
    {},
  );
  const kinds = (Object.keys(KIND_WORD) as Annotation["marks"][number]["kind"][])
    .filter((k) => (counts[k] ?? 0) > 0)
    .map((k) => `${counts[k] ?? 0} ${KIND_WORD[k]}${(counts[k] ?? 0) === 1 ? "" : "s"}`)
    .join(", ");
  const replaced = a.replaces === null ? "" : ` · replaces #${a.replaces}`;
  const signed = a.signed_seq === null ? " · not yet signed" : ` · signed by entry #${a.signed_seq}`;
  return `${a.marks.length} marks (${kinds}) on the ${a.role} image${replaced}${signed}`;
}

interface Props {
  jobId: string;
  onFailure: (error: unknown) => void;
  notify?: (message: string) => void;
  /** Bumped by the parent when a set was added, so the list reloads. */
  version?: number;
}

export function AnnotationsPanel({ jobId, onFailure, notify, version = 0 }: Props) {
  const [sets, setSets] = useState<Annotation[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    ipc
      .listAnnotations(jobId)
      .then((found) => {
        if (live) {
          setSets(found);
        }
      })
      .catch((error: unknown) => {
        if (live) {
          setSets([]);
          onFailure(error);
        }
      });
    return () => {
      live = false;
    };
  }, [jobId, version, onFailure]);

  const save = async (a: Annotation) => {
    setBusy(a.seq);
    try {
      const done = await ipc.exportAnnotated(a.seq, `annotated-${a.sha256.slice(0, 12)}-set-${a.seq}.png`);
      notify?.(
        `Wrote the annotated image with ${done.marks} marks; SHA-256 ${done.sha256.slice(0, 12)} is in the custody log.`,
      );
    } catch (error) {
      if (!(error instanceof IpcError && error.kind === "cancelled")) {
        onFailure(error);
      }
    } finally {
      setBusy(null);
    }
  };

  if (sets === null) {
    return <p className="muted">Loading annotations...</p>;
  }
  const replaced = new Set(sets.map((a) => a.replaces).filter((r): r is number => r !== null));
  return (
    <section className="card annotations" aria-labelledby={`annotations-${jobId}`}>
      <h3 id={`annotations-${jobId}`}>Examiner annotations</h3>
      <p className="muted">{ANNOTATIONS_NOTE}</p>
      {sets.length === 0 ? (
        <p className="empty">No marks recorded on this job's images yet.</p>
      ) : (
        <ol className="annotation-sets">
          {sets.map((a) => (
            <li key={a.seq} className={replaced.has(a.seq) ? "annotation-replaced" : undefined}>
              <span>
                <code>#{a.seq}</code> {a.ts_utc} · {a.actor} · <Hash value={a.sha256} length={12} />
                {replaced.has(a.seq) ? " · replaced by a later set" : ""}
              </span>
              <span className="muted">{setLine(a)}</span>
              {a.note ? <span className="annotation-note">{a.note}</span> : null}
              <Button
                onClick={() => {
                  void save(a);
                }}
                busy={busy === a.seq}
                aria-label={`Save annotated image of set ${a.seq}`}
              >
                Save annotated image...
              </Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
