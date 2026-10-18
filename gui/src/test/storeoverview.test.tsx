import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StoreScreen } from "../screens/StoreScreen";
import { axeViolations, routes } from "./ipc";

const IDS = ["0f8fad5b-d9cb-469f-a165-70867728950e", "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1"];
const STORE = {
  path: "C:/cases",
  identity: { exists: true as const, key_id: "0123456789abcdef", public_key: "AAAA" },
  cases: IDS.map((case_id) => ({ case_id, state: "active" as const, created_utc: null, disposed_utc: null })),
};
const OVERVIEW = [
  {
    case_id: IDS[0],
    state: "active",
    reference: "KT-2026-1",
    retention_until: "2031-01-01",
    legal_hold: true,
    due: false,
    evidence: 1,
    jobs: 2,
    problem: null,
  },
  {
    case_id: IDS[1],
    state: "active",
    reference: "KT-2026-2",
    retention_until: "2020-01-01",
    legal_hold: false,
    due: true,
    evidence: 3,
    jobs: 0,
    problem: null,
  },
];

describe("case details", () => {
  it("shows references, retention dates and holds after the passphrase prompt", async () => {
    const mocked = routes({ store_overview: () => OVERVIEW });
    const { container, rerender } = render(
      <StoreScreen store={STORE} notice={null} onStore={vi.fn()} onOpened={vi.fn()} />,
    );
    expect(screen.queryByText("KT-2026-1")).toBeNull(); // encrypted until the passphrase is entered
    await userEvent.click(screen.getByRole("button", { name: "Show case details..." }));
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    const [first, second] = rows as [HTMLElement, HTMLElement];
    expect(first).toHaveTextContent("KT-2026-1");
    expect(within(first).getByText("Legal hold")).toBeInTheDocument();
    expect(first).toHaveTextContent("Keep until 2031-01-01");
    expect(first).toHaveTextContent("1 evidence photo");
    expect(within(second).getByText("Retention date reached")).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("store_overview", {});
    expect(screen.queryByRole("button", { name: "Show case details..." })).toBeNull();
    expect(await axeViolations(container)).toEqual([]);
    rerender(
      <StoreScreen
        store={{ ...STORE, path: "D:/other" }}
        notice={null}
        onStore={vi.fn()}
        onOpened={vi.fn()}
      />,
    );
    expect(screen.queryByText("KT-2026-1")).toBeNull(); // details belong to the store they came from
  });
});
