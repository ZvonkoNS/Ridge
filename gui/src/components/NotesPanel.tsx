// Examiner notes: contemporaneous observations about the case or one job, kept in the custody log.
// Notes cannot be changed or removed; a correction is a new note naming the one it corrects, and
// the original stays readable. Ridge keeps the text as written and never interprets it.
import { useEffect, useId, useState } from "react";

import { ipc } from "../ipc/commands";
import type { Note } from "../ipc/types";
import { Button, utc } from "./ui";

export const MAX_NOTE_CHARS = 2000;

interface Props {
  /** A job's notes, or every note of the case when null. */
  jobId: string | null;
  onFailure: (error: unknown) => void;
}

function NoteLine({ note, showJob, onCorrect }: { note: Note; showJob: boolean; onCorrect: () => void }) {
  return (
    <li className="note">
      <p className="note-meta">
        #{note.seq} · {utc(note.ts_utc)} · {note.actor}
        {showJob && note.job_id ? ` · job ${note.job_id.slice(0, 8)}` : ""}
        {note.corrects !== null ? ` · corrects #${note.corrects}` : ""}
      </p>
      <p className="note-text">{note.text}</p>
      <Button className="note-correct" onClick={onCorrect} aria-label={`Correct note ${note.seq}`}>
        Correct...
      </Button>
    </li>
  );
}

export function NotesPanel({ jobId, onFailure }: Props) {
  const titleId = useId();
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [text, setText] = useState("");
  const [corrects, setCorrects] = useState<Note | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    ipc.listNotes(jobId).then(setNotes, onFailure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const add = async () => {
    setBusy(true);
    try {
      const note = await ipc.addNote(text, jobId, corrects?.seq ?? null);
      setNotes((shown) => [...(shown ?? []), note]);
      setText("");
      setCorrects(null);
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="notes" aria-labelledby={titleId}>
      <h3 id={titleId}>{jobId ? "Examiner notes on this job" : "Examiner notes"}</h3>
      <p className="muted">
        Each note is added to the custody log with your name and the time. Notes cannot be changed or removed;
        a correction is added as a new note and the original stays.
      </p>
      {notes?.length === 0 ? <p className="empty">No notes yet.</p> : null}
      {notes && notes.length > 0 ? (
        <ol className="notes-list">
          {notes.map((n) => (
            <NoteLine
              key={n.seq}
              note={n}
              showJob={jobId === null}
              onCorrect={() => {
                setCorrects(n);
              }}
            />
          ))}
        </ol>
      ) : null}
      <form
        className="notes-form"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <label className="field">
          <span>{corrects ? `Correction of note #${corrects.seq}` : "New note"}</span>
          <textarea
            rows={3}
            maxLength={MAX_NOTE_CHARS}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
            }}
          />
        </label>
        <div className="notes-actions">
          {corrects ? (
            <Button
              onClick={() => {
                setCorrects(null);
              }}
            >
              Cancel correction
            </Button>
          ) : null}
          <Button type="submit" variant="primary" busy={busy} disabled={text.trim() === ""}>
            {corrects ? "Add correction" : "Add note"}
          </Button>
        </div>
      </form>
    </section>
  );
}
