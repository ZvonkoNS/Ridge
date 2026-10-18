import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StoreScreen } from "../screens/StoreScreen";
import { axeViolations, routes } from "./ipc";

const STORE = {
  path: "C:/cases",
  identity: { exists: true as const, key_id: "0123456789abcdef", public_key: "AAAA" },
  cases: [
    {
      case_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
      state: "active" as const,
      created_utc: null,
      disposed_utc: null,
    },
    {
      case_id: "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1",
      state: "active" as const,
      created_utc: null,
      disposed_utc: null,
    },
  ],
};

describe("verify all cases", () => {
  it("names every case and shows failures with their problems", async () => {
    const mocked = routes({
      verify_store: () => [
        { ...STORE.cases[0], checked: true, ok: true, reference: "KT-1", items: 3, reports: 1, problems: [] },
        {
          ...STORE.cases[1],
          checked: true,
          ok: false,
          reference: "KT-2",
          items: 2,
          reports: 0,
          problems: ["evidence 3f9a1c2e0000 (finger.png): stored evidence does not match its hash"],
        },
      ],
      refresh_store: () => STORE,
    });
    const { container, rerender } = render(
      <StoreScreen store={STORE} notice={null} onStore={vi.fn()} onOpened={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Verify all cases..." }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("1 of 2 cases verified; 1 with problems");
    expect(alert).toHaveTextContent("KT-2 FAILED: evidence 3f9a1c2e0000");
    expect(alert).toHaveTextContent("KT-1 verified: 3 items, 1 signed reports");
    expect(mocked).toHaveBeenCalledWith("verify_store", {});
    expect(await axeViolations(container)).toEqual([]);
    rerender(
      <StoreScreen
        store={{ ...STORE, path: "D:/other" }}
        notice={null}
        onStore={vi.fn()}
        onOpened={vi.fn()}
      />,
    );
    expect(screen.queryByText(/cases verified/)).toBeNull(); // results belong to the store they came from
  });
});
