// Vitest setup: DOM matchers, a clean DOM after each test, and the browser APIs jsdom lacks.
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

if (typeof URL.createObjectURL !== "function") {
  let next = 0;
  URL.createObjectURL = vi.fn(() => {
    next += 1;
    return `blob:test/${next}`;
  });
  URL.revokeObjectURL = vi.fn();
}

if (typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// The Tauri IPC bridge does not exist in tests; every test routes commands itself (src/test/ipc.ts).
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
