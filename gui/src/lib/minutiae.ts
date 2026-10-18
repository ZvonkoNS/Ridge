// Minutiae overlay data (FR-40): Ridge's unvalidated automatic markings, drawn over the print or
// the comparison export for orientation only. Never used for matching; the overlay changes no
// pixel. Coordinates come from the job's own minutiae artefact, in the space of the shown image.
import { useEffect, useState } from "react";

import { ipc } from "../ipc/commands";
import type { MinutiaeSpace, MinutiaeView, Role } from "../ipc/types";
import type { Size } from "./viewport";

export const MINUTIAE_NOTE =
  "Minutiae overlay: unvalidated automatic markings for orientation only, never used for matching.";

export interface Mark {
  x: number;
  y: number;
  kind: "ending" | "bifurcation";
  angle: number;
}

export interface Marks {
  items: Mark[];
  /** Marker radius in image pixels (about half a ridge period). */
  size: number;
}

/** The marks for the shown image, or null when its role or size does not match the artefact. */
export function marksFor(view: MinutiaeView | null, role: Role, shown: Size | null): Marks | null {
  if (!view || !shown) {
    return null;
  }
  const space: MinutiaeSpace | null = role === "export" ? view.export : role === "print" ? view.print : null;
  if (space?.width !== shown.width || space.height !== shown.height) {
    return null;
  }
  return {
    size: Math.max(2, space.ridge_period_px * 0.45),
    items: space.minutiae.map((m) => ({ x: m.x, y: m.y, kind: m.type, angle: m.angle_deg })),
  };
}

/** Fetch a minutiae artefact when `sha256` is set (a logged read); null until it arrives. */
export function useMinutiae(sha256: string | null, onError: (error: unknown) => void): MinutiaeView | null {
  const [state, setState] = useState<{ sha256: string; view: MinutiaeView } | null>(null);
  useEffect(() => {
    if (!sha256) {
      return undefined;
    }
    let cancelled = false;
    ipc.minutiae(sha256).then(
      (view) => {
        if (!cancelled) {
          setState({ sha256, view });
        }
      },
      (error: unknown) => {
        if (!cancelled) {
          onError(error);
        }
      },
    );
    return () => {
      cancelled = true;
    };
    // onError is a callback prop; refetching when it changes would repeat a logged read
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sha256]);
  return sha256 !== null && state?.sha256 === sha256 ? state.view : null;
}
