import { invoke } from "@tauri-apps/api/core";
import { describe, expect, it, vi } from "vitest";

import { IpcError, ipc, isLocked, promptIpc } from "../ipc/commands";
import { liveCount, pngUrl, revokeAll } from "../ipc/images";
import { ipcError, routes } from "./ipc";

describe("IPC wrappers", () => {
  it("wraps arguments in one request object and never sends paths", async () => {
    const mocked = routes({ export_item: () => ({ exported: "C:/out/x.png" }) });
    await ipc.exportItem("b".repeat(64), "x.png");
    expect(mocked).toHaveBeenCalledWith("export_item", {
      request: { sha256: "b".repeat(64), suggested_name: "x.png" },
    });
    routes({ choose_store: () => ({ path: "C:/store", identity: { exists: false }, cases: [] }) });
    await ipc.chooseStore();
    expect(vi.mocked(invoke)).toHaveBeenLastCalledWith("choose_store", {});
  });

  it("maps core errors to typed errors", async () => {
    routes({ list_items: () => ipcError("refused", "no case is unlocked") });
    const error = await ipc.listItems().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(IpcError);
    expect(error).toMatchObject({ kind: "refused", message: "no case is unlocked" });
    expect(isLocked(error)).toBe(true);
  });

  it("treats anything malformed as an unavailable core", async () => {
    routes({ case_info: () => ipcError("root", "forged") });
    const error = await ipc.caseInfo().catch((e: unknown) => e);
    expect(error).toMatchObject({ kind: "unavailable" });
    expect(isLocked(new IpcError("refused", "the ruler points must be apart"))).toBe(false);
  });

  it("sends the passphrase to the prompt command only", async () => {
    const mocked = routes({ passphrase_submit: () => null });
    await promptIpc.submit("correct horse battery staple", null);
    expect(mocked).toHaveBeenCalledWith("passphrase_submit", {
      request: { passphrase: "correct horse battery staple", confirmation: null },
    });
  });
});

describe("preview memory", () => {
  it("revokes every preview URL when the case closes", () => {
    pngUrl(btoa("PNG"));
    pngUrl(btoa("PNG"));
    expect(liveCount()).toBe(2);
    revokeAll();
    expect(liveCount()).toBe(0);
  });
});
