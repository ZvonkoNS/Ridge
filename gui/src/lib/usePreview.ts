// Load a stored image's bounded preview as a blob: URL, released when the item changes or the
// component unmounts. Each load is a logged read in the custody log (FR-22).
import { useEffect, useState } from "react";

import { ipc } from "../ipc/commands";
import { pngUrl, revoke } from "../ipc/images";
import type { Size } from "./viewport";

export const PREVIEW_SIDE = 2048;

export interface LoadedPreview {
  url: string | null;
  bitmap: Size | null;
  source: Size | null;
  ppi: number | null;
  error: unknown;
}

const EMPTY: LoadedPreview = { url: null, bitmap: null, source: null, ppi: null, error: null };

export function usePreview(sha256: string | null, onError?: (error: unknown) => void): LoadedPreview {
  // The loaded preview remembers which item it belongs to; a stale one is never returned.
  const [state, setState] = useState<LoadedPreview & { sha256: string | null }>({ ...EMPTY, sha256: null });
  useEffect(() => {
    if (!sha256) {
      return undefined;
    }
    let cancelled = false;
    let url: string | null = null;
    ipc
      .preview(sha256, PREVIEW_SIDE)
      .then((p) => {
        url = pngUrl(p.png_base64);
        if (cancelled) {
          revoke(url);
          return;
        }
        setState({
          sha256,
          url,
          bitmap: { width: p.width, height: p.height },
          source: { width: p.source_width, height: p.source_height },
          ppi: p.ppi ?? null,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ ...EMPTY, sha256, error });
          onError?.(error);
        }
      });
    return () => {
      cancelled = true;
      if (url) {
        revoke(url);
      }
    };
    // onError is a callback prop; reloading the image when it changes would repeat a logged read
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sha256]);
  return sha256 !== null && state.sha256 === sha256 ? state : EMPTY;
}
