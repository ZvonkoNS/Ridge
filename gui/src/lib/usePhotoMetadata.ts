// Load an imported photo's metadata once per item (each load is a logged read in the custody log,
// FR-22). A stale answer for another item is never returned.
import { useEffect, useState } from "react";

import { ipc } from "../ipc/commands";
import type { PhotoMetadata, ProvenanceHints } from "../ipc/types";

export interface LoadedMetadata {
  metadata: PhotoMetadata | null;
  provenance: ProvenanceHints | null;
  loading: boolean;
  failed: boolean;
}

const IDLE: LoadedMetadata = { metadata: null, provenance: null, loading: false, failed: false };

export function usePhotoMetadata(sha256: string | null, onError?: (error: unknown) => void): LoadedMetadata {
  const [state, setState] = useState<LoadedMetadata & { sha256: string | null }>({ ...IDLE, sha256: null });
  useEffect(() => {
    if (!sha256) {
      return undefined;
    }
    let cancelled = false; // until the answer arrives, the hook reports `loading` (see below)
    ipc.photoMetadata(sha256).then(
      (view) => {
        if (!cancelled) {
          setState({
            metadata: view.metadata,
            provenance: view.provenance ?? null,
            loading: false,
            failed: false,
            sha256,
          });
        }
      },
      (error: unknown) => {
        if (!cancelled) {
          setState({ ...IDLE, failed: true, sha256 });
          onError?.(error);
        }
      },
    );
    return () => {
      cancelled = true;
    };
    // onError is a callback prop; reloading when it changes would repeat a logged read
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sha256]);
  if (sha256 === null) {
    return IDLE;
  }
  return state.sha256 === sha256 ? state : { ...IDLE, loading: true }; // before the first answer
}
