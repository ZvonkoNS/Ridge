// The minutiae overlay switch for an output viewer. Off by default; turning it on reads the job's
// minutiae artefact once (a logged read) and states, while shown, that the markings are unvalidated.
import { useState } from "react";

import type { Role } from "../ipc/types";
import { MINUTIAE_NOTE, marksFor, useMinutiae, type Marks } from "../lib/minutiae";
import type { Size } from "../lib/viewport";

export interface Overlay {
  available: boolean;
  on: boolean;
  setOn: (on: boolean) => void;
  marks: Marks | null;
}

/** Overlay state for the shown output (`role`, `shown` size) of a job with a minutiae artefact. */
export function useMinutiaeOverlay(
  minutiaeSha: string | null,
  role: Role | null,
  shown: Size | null,
  onError: (error: unknown) => void,
): Overlay {
  const [on, setOn] = useState(false);
  const available = minutiaeSha !== null && (role === "print" || role === "export");
  const view = useMinutiae(on && available ? minutiaeSha : null, onError);
  const marks = on && available ? marksFor(view, role, shown) : null;
  return { available, on, setOn, marks };
}

export function MinutiaeToggle({ overlay }: { overlay: Overlay }) {
  if (!overlay.available) {
    return null;
  }
  return (
    <label className="overlay-toggle">
      <input
        type="checkbox"
        checked={overlay.on}
        onChange={(e) => {
          overlay.setOn(e.target.checked);
        }}
      />
      Show minutiae (unvalidated)
    </label>
  );
}

export function MinutiaeNote({ overlay }: { overlay: Overlay }) {
  return overlay.on && overlay.marks ? (
    <p className="overlay-note" role="note">
      {MINUTIAE_NOTE} Circle: ending. Square: bifurcation. {overlay.marks.items.length} shown.
    </p>
  ) : null;
}
