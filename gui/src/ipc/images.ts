// Previews arrive as bounded base64 PNGs and are shown as blob: URLs (CSP img-src 'self' blob:).
// They live in memory only: never in localStorage, IndexedDB or caches, and every URL is revoked
// when the case closes (desktop_gui_tauri_standards.md §6).

const live = new Set<string>();

/** Decode a base64 PNG into a blob: URL that `revokeAll` will release. */
export function pngUrl(base64: string): string {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
  live.add(url);
  return url;
}

export function revoke(url: string): void {
  if (live.delete(url)) {
    URL.revokeObjectURL(url);
  }
}

/** Release every preview (case locked or closed). */
export function revokeAll(): void {
  for (const url of live) {
    URL.revokeObjectURL(url);
  }
  live.clear();
}

export function liveCount(): number {
  return live.size;
}
