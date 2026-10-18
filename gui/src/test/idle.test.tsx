import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { idleState, noteActivity } from "../lib/idle";
import { CaseScreen } from "../screens/CaseScreen";
import { routes } from "./ipc";

const SESSION = {
  case_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
  reference: "KT-2026-0001",
  retention_until: "2027-01-31",
  legal_hold: false,
};

afterEach(() => {
  vi.useRealTimers();
});

describe("idle lock", () => {
  it("counts down only in the last minute and expires on time", () => {
    expect(idleState(100_000, 100_000, 900, 60)).toEqual({ secondsLeft: null, expired: false });
    expect(idleState(100_000 + 845_000, 100_000, 900, 60)).toEqual({ secondsLeft: 55, expired: false });
    expect(idleState(100_000 + 900_000, 100_000, 900, 60)).toEqual({ secondsLeft: 0, expired: true });
  });

  it("warns, can be kept open, and locks the case itself when time runs out", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const lock = vi.fn(() => ({ locked: true }));
    const status = vi.fn(() => ({ unlocked: true, idle_timeout_s: 120 }));
    routes({
      list_items: () => [],
      case_info: () => ({ ...SESSION, legal_basis: "synthetic" }),
      limits_of_use: () => ({ configured: false }),
      session_status: status,
      lock_case: lock,
    });
    const onClosed = vi.fn();
    render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={onClosed} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    act(() => {
      noteActivity(Date.now() - 70_000); // 70 s of a 120 s timeout already passed
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_100);
    });
    expect(screen.getByRole("alert")).toHaveTextContent("the case locks in");
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
    await user.click(screen.getByRole("button", { name: "Keep the case open" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50); // the engine's answer restarts the idle clock
    });
    expect(status).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/the case locks in/)).toBeNull();
    act(() => {
      noteActivity(Date.now() - 125_000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_100);
    });
    expect(lock).toHaveBeenCalled();
    expect(onClosed).toHaveBeenCalledWith(expect.stringContaining("2 minutes without activity"));
  });
});
