// Marking minutiae on a job's output (FR-56): the examiner clicks on the output viewer to place
// numbered marks, removes or labels them, and saves the set, which the sidecar records as a signed
// custody entry (FR-55). Saved marks of the latest set are drawn too. Nothing here interprets a mark.
import { useEffect, useRef, useState } from "react";

import { ipc } from "../ipc/commands";
import type { Annotation, AnnotationMark, Role } from "../ipc/types";
import type { Marks } from "../lib/minutiae";
import type { Point, Size } from "../lib/viewport";
import { ANNOTATIONS_NOTE } from "./AnnotationsPanel";
import { Button } from "./ui";

export type MarkKind = AnnotationMark["kind"];
/** The kinds an examiner can mark, as shown in the radio group. */
export const KIND_LABELS: Record<MarkKind, string> = {
  ending: "Ending",
  bifurcation: "Bifurcation",
  other: "Other",
};
/** Only the job's own output images can be annotated (FR-55); references and evidence cannot. */
export const MARKABLE_ROLES: readonly Role[] = ["print", "export", "export-gray"];
/** The sidecar's limit for a mark's label. */
export const MAX_LABEL_CHARS = 40;

export interface DraftMark {
  n: number;
  x: number;
  y: number;
  kind: MarkKind;
  label: string | null;
}

/** Marks numbered 1..n in order. */
export function renumber(list: Omit<DraftMark, "n">[]): DraftMark[] {
  return list.map((m, i) => ({ ...m, n: i + 1 }));
}

/** The current (not replaced) set on `sha256` with the highest seq, or null. */
export function latestSet(sets: Annotation[], sha256: string): Annotation | null {
  const replaced = new Set(sets.map((a) => a.replaces).filter((r): r is number => r !== null));
  const current = sets.filter((a) => a.sha256 === sha256 && !replaced.has(a.seq));
  return current.reduce<Annotation | null>((best, a) => (best === null || a.seq > best.seq ? a : best), null);
}

interface Image {
  sha256: string;
  role: Role;
}

/**
 * Marking state for one output image: the mark tool's switch, the kind and label of the next mark, the unsaved
 * marks, the note, the latest saved set, and the save through FR-55. Everything stays in memory until saved.
 */
export function useMarking(
  jobId: string | null,
  image: Image | null,
  shown: Size | null,
  onFailure: (error: unknown) => void,
  notify?: (message: string) => void,
) {
  const enabled = jobId !== null && image !== null && MARKABLE_ROLES.includes(image.role);
  const [marking, setMarking] = useState(false);
  const [kind, setKind] = useState<MarkKind>("ending");
  const [label, setLabel] = useState("");
  const [draft, setDraft] = useState<DraftMark[]>([]);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<Annotation | null>(null);
  const [showSaved, setShowSaved] = useState(true);
  const [saving, setSaving] = useState(false);
  const sha256 = image?.sha256 ?? null;
  const onScreen = useRef(sha256); // the image on screen, for a save that completes after a switch
  useEffect(() => {
    onScreen.current = sha256;
  }, [sha256]);

  // A different image gets its own draft and saved set (the pattern ImageViewer uses for a new url).
  const [forImage, setForImage] = useState(sha256);
  if (forImage !== sha256) {
    setForImage(sha256);
    setDraft([]);
    setSaved(null);
  }

  useEffect(() => {
    if (jobId === null || sha256 === null) {
      return undefined;
    }
    let live = true;
    ipc
      .listAnnotations(jobId, sha256)
      .then((sets) => {
        if (live) {
          setSaved(latestSet(sets, sha256));
        }
      })
      .catch((error: unknown) => {
        if (live) {
          onFailure(error);
        }
      });
    return () => {
      live = false;
    };
  }, [jobId, sha256, onFailure]);

  const addAt = (p: Point) => {
    if (!marking || !enabled) {
      return;
    }
    const text = label.trim();
    setDraft((d) => [...d, { n: d.length + 1, x: p.x, y: p.y, kind, label: text === "" ? null : text }]);
  };
  const remove = (n: number) => {
    setDraft((d) => renumber(d.filter((m) => m.n !== n)));
  };
  const save = async () => {
    if (jobId === null || sha256 === null || draft.length === 0) {
      return;
    }
    setSaving(true);
    const target = sha256;
    const snapshot = draft;
    try {
      const marks = snapshot.map(({ x, y, kind: k, label: l }) => ({ x, y, kind: k, label: l }));
      const trimmed = note.trim();
      const recorded = await ipc.addAnnotation(
        jobId,
        sha256,
        marks,
        trimmed === "" ? null : trimmed,
        saved?.seq ?? null,
      );
      if (onScreen.current === target) {
        setSaved(recorded);
        setDraft((d) => d.filter((m) => !snapshot.includes(m))); // marks placed meanwhile stay unsaved
        setNote("");
      }
      notify?.(
        `Annotation set #${recorded.seq} recorded with ${recorded.marks.length} marks and signed by entry #${recorded.signed_seq ?? "?"}.`,
      );
    } catch (error) {
      onFailure(error);
    } finally {
      setSaving(false);
    }
  };

  const size = shown ? Math.max(4, Math.round(shown.width / 150)) : 6;
  const items: Marks["items"] = [
    ...(showSaved && saved
      ? saved.marks.map((m) => ({ x: m.x, y: m.y, kind: m.kind, angle: null, label: `${m.n}` }))
      : []),
    ...draft.map((m) => ({ x: m.x, y: m.y, kind: m.kind, angle: null, label: `${m.n}*` })),
  ];
  return {
    enabled,
    marking: marking && enabled,
    toggle: () => {
      setMarking((m) => !m);
    },
    kind,
    setKind,
    label,
    setLabel,
    draft,
    addAt,
    remove,
    note,
    setNote,
    save,
    saving,
    saved,
    showSaved,
    setShowSaved,
    examinerMarks: items.length > 0 ? { items, size } : null,
    canSave: enabled && draft.length > 0 && !saving,
  };
}

export type Marking = ReturnType<typeof useMarking>;

/** The controls under the output viewer for `useMarking`. Renders nothing for an image that cannot be annotated. */
export function MarkingPanel({ m }: { m: Marking }) {
  if (!m.enabled) {
    return null;
  }
  return (
    <section className="card marking-panel" aria-label="Mark minutiae">
      <div className="marking-head">
        <Button
          variant={m.marking ? "primary" : "quiet"}
          aria-pressed={m.marking}
          onClick={() => {
            m.toggle();
          }}
        >
          {m.marking ? "Marking: click the output to place a mark" : "Mark minutiae"}
        </Button>
        {m.saved ? (
          <label className="check">
            <input
              type="checkbox"
              checked={m.showSaved}
              onChange={(e) => {
                m.setShowSaved(e.target.checked);
              }}
            />
            <span>
              Show saved marks (set #{m.saved.seq}, {m.saved.marks.length} marks)
            </span>
          </label>
        ) : null}
      </div>
      {m.marking ? (
        <div className="marking-tools" role="group" aria-label="Next mark">
          <fieldset className="marking-kind">
            <legend>Kind of the next mark</legend>
            {(Object.keys(KIND_LABELS) as MarkKind[]).map((k) => (
              <label key={k} className={`tool${m.kind === k ? " tool-on" : ""}`}>
                <input
                  type="radio"
                  name="mark-kind"
                  value={k}
                  checked={m.kind === k}
                  onChange={() => {
                    m.setKind(k);
                  }}
                />
                {KIND_LABELS[k]}
              </label>
            ))}
          </fieldset>
          <label className="field">
            <span>Label for the next mark (optional)</span>
            <input
              value={m.label}
              maxLength={MAX_LABEL_CHARS}
              onChange={(e) => {
                m.setLabel(e.target.value);
              }}
            />
          </label>
        </div>
      ) : null}
      {m.draft.length > 0 ? (
        <>
          <ol className="draft-marks" aria-label="Unsaved marks">
            {m.draft.map((d) => (
              <li key={d.n}>
                <span>
                  {d.n}: {KIND_LABELS[d.kind]} at ({d.x}, {d.y}){d.label ? ` · ${d.label}` : ""}
                </span>
                <button
                  type="button"
                  className="link-button"
                  aria-label={`Remove mark ${d.n}`}
                  onClick={() => {
                    m.remove(d.n);
                  }}
                >
                  Remove
                </button>
              </li>
            ))}
          </ol>
          <label className="field">
            <span>Note on this set (optional)</span>
            <textarea
              value={m.note}
              maxLength={2000}
              rows={2}
              onChange={(e) => {
                m.setNote(e.target.value);
              }}
            />
          </label>
          <Button variant="primary" busy={m.saving} disabled={!m.canSave} onClick={() => void m.save()}>
            {`Save ${m.draft.length} ${m.draft.length === 1 ? "mark" : "marks"}`}
            {m.saved ? ` (replaces set #${m.saved.seq})` : ""}
          </Button>
        </>
      ) : null}
      <p className="muted">{ANNOTATIONS_NOTE} Unsaved marks are numbered with an asterisk.</p>
    </section>
  );
}
