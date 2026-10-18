import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { PassphrasePrompt } from "../passphrase/PassphrasePrompt";
import { CaseScreen } from "../screens/CaseScreen";
import { axeViolations, ipcError, routes } from "./ipc";

const CASE_ID = "0f8fad5b-d9cb-469f-a165-70867728950e";
const SESSION = {
  case_id: CASE_ID,
  reference: "KT-2026-0001",
  retention_until: "2027-01-31",
  legal_hold: false,
};
const INFO = { ...SESSION, legal_basis: "Synthetic test basis" };
const EVIDENCE = {
  sha256: "e".repeat(64),
  role: "evidence",
  size: 2048,
  label: "finger.png",
  job_id: null,
  source: "Exhibit 3",
};

describe("store screen", () => {
  it("leads a first run to the identity and keeps the passphrase out of this window", async () => {
    let identity = false;
    const mocked = routes({
      choose_store: () => ({ path: "C:/cases", identity: { exists: false }, cases: [] }),
      create_identity: () => {
        identity = true;
        return { key_id: "0123456789abcdef", public_key: "AAAA" };
      },
      refresh_store: () =>
        identity
          ? {
              path: "C:/cases",
              identity: { exists: true, key_id: "0123456789abcdef", public_key: "AAAA" },
              cases: [],
            }
          : ipcError("no_store", "choose a case store first"),
    });
    const { container } = render(<App />);
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "Choose case store..." }));
    await userEvent.click(await screen.findByRole("button", { name: "Create examiner identity..." }));
    expect(await screen.findByText("No cases in this store yet.")).toBeInTheDocument();
    expect(container.querySelector("input[type=password]")).toBeNull();
    expect(mocked).toHaveBeenCalledWith("create_identity", {});
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows the store the core remembered, without a dialog", async () => {
    routes({
      refresh_store: () => ({
        path: "C:/cases",
        identity: { exists: true, key_id: "0123456789abcdef", public_key: "AAAA" },
        cases: [],
      }),
    });
    render(<App />);
    expect(await screen.findByText("C:/cases")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose another store..." })).toBeInTheDocument();
  });

  it("unlocks a listed case and shows its tag", async () => {
    routes({
      choose_store: () => ({
        path: "C:/cases",
        identity: { exists: true, key_id: "0123456789abcdef", public_key: "AAAA" },
        cases: [
          { case_id: CASE_ID, state: "active", created_utc: "2026-10-17T10:00:00Z", disposed_utc: null },
        ],
      }),
      unlock_case: (request) => {
        expect(request).toEqual({ case_id: CASE_ID });
        return SESSION;
      },
      list_items: () => [],
      case_info: () => INFO,
      limits_of_use: () => ({ configured: false }),
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Choose case store..." }));
    await userEvent.click(await screen.findByRole("button", { name: "Unlock..." }));
    expect(await screen.findByLabelText("Case KT-2026-0001")).toBeInTheDocument();
    expect(await screen.findByText("Synthetic test basis")).toBeInTheDocument();
  });

  it("says nothing when the examiner cancels the prompt", async () => {
    routes({
      choose_store: () => ({
        path: "C:/cases",
        identity: { exists: true, key_id: "0123456789abcdef", public_key: "AAAA" },
        cases: [{ case_id: CASE_ID, state: "active", created_utc: null, disposed_utc: null }],
      }),
      unlock_case: () => ipcError("cancelled", "cancelled"),
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Choose case store..." }));
    await userEvent.click(await screen.findByRole("button", { name: "Unlock..." }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Unlock..." })).toBeEnabled();
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("case screen", () => {
  it("returns to the store when the case was locked behind its back", async () => {
    routes({
      list_items: () => [EVIDENCE],
      case_info: () => INFO,
      limits_of_use: () => ({ configured: false }),
      preview: () => ipcError("refused", "no case is unlocked"),
    });
    const onClosed = vi.fn();
    const { container } = render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={onClosed} />);
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(await screen.findByRole("button", { name: /finger\.png/ }));
    await waitFor(() => {
      expect(onClosed).toHaveBeenCalledWith(expect.stringContaining("The case was locked"));
    });
  });

  it("shows refusals from Ridge as alerts", async () => {
    routes({
      list_items: () => [],
      case_info: () => INFO,
      limits_of_use: () => ({ configured: false }),
      verify_case: () => ipcError("refused", "custody entry 12 does not match its hash"),
    });
    render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Records/ }));
    await userEvent.click(screen.getByRole("button", { name: "Verify now" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("custody entry 12 does not match its hash");
  });

  it("never writes case data to WebView storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    routes({
      list_items: () => [EVIDENCE],
      case_info: () => INFO,
      limits_of_use: () => ({ configured: false }),
      preview: () => ipcError("refused", "x"),
    });
    render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /finger\.png/ }));
    expect(setItem).not.toHaveBeenCalled();
  });
});

describe("passphrase prompt", () => {
  it("asks for a confirmed, long passphrase on first run and clears it after use", async () => {
    const submit = vi.fn(() => ipcError("refused", "the passphrase is too common"));
    routes({
      passphrase_context: () => ({
        purpose: "create_identity",
        title: "Choose your examiner passphrase",
        detail: "It cannot be recovered.",
        confirm: true,
        min_chars: 15,
        attempts_left: 5,
      }),
      passphrase_submit: submit,
    });
    const { container } = render(<PassphrasePrompt />);
    const first = await screen.findByLabelText("New passphrase");
    const create = screen.getByRole("button", { name: "Create identity" });
    await userEvent.type(first, "short");
    expect(screen.getByText(/at least 15 characters/)).toBeInTheDocument();
    expect(create).toBeDisabled();
    await userEvent.clear(first);
    await userEvent.type(first, "correct horse battery staple");
    await userEvent.type(screen.getByLabelText("Type it again"), "correct horse battery");
    expect(create).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Type it again"), " staple");
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(create);
    expect(submit).toHaveBeenCalledWith({
      passphrase: "correct horse battery staple",
      confirmation: "correct horse battery staple",
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("the passphrase is too common");
    expect(first).toHaveValue("");
  });

  it("cancels through the core", async () => {
    const cancel = vi.fn(() => null);
    routes({
      passphrase_context: () => ({
        purpose: "unlock",
        title: "Unlock case",
        detail: "Case 0f8fad5b.",
        confirm: false,
        min_chars: 1,
        attempts_left: 5,
      }),
      passphrase_cancel: cancel,
    });
    render(<PassphrasePrompt />);
    expect(await screen.findByRole("heading", { name: "Unlock case" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Type it again")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(cancel).toHaveBeenCalled();
  });
});
