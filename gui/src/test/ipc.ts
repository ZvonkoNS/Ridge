// Route mocked Tauri commands to handlers; an unexpected command fails the test loudly.
import { invoke } from "@tauri-apps/api/core";
import axe from "axe-core";
import { vi } from "vitest";

type Handler = (request: Record<string, unknown> | undefined) => unknown;

export function routes(map: Record<string, Handler>): ReturnType<typeof vi.mocked<typeof invoke>> {
  const mocked = vi.mocked(invoke);
  mocked.mockImplementation((command: string, args?: unknown) => {
    const handler = map[command];
    if (!handler) {
      return Promise.reject(new Error(`unexpected command ${command}`));
    }
    const request = (args as { request?: Record<string, unknown> } | undefined)?.request;
    try {
      return Promise.resolve(handler(request));
    } catch (error) {
      // the Rust core rejects with a plain { kind, message } object, not an Error
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      return Promise.reject(error);
    }
  });
  return mocked;
}

/** An error as the Rust core serialises it. */
export function ipcError(kind: string, message: string): never {
  // eslint-disable-next-line @typescript-eslint/only-throw-error -- the Rust core rejects with a plain object
  throw { kind, message };
}

/** Accessibility check of a rendered tree (colour contrast is reviewed manually: jsdom has no layout). */
export async function axeViolations(container: Element): Promise<string[]> {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  return result.violations.map((v) => `${v.id}: ${v.help}`);
}
