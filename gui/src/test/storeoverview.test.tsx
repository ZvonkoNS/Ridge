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

  it("finds a case by reference once the details are shown", async () => {
    routes({ store_overview: () => OVERVIEW });
    render(<StoreScreen store={STORE} notice={null} onStore={vi.fn()} onOpened={vi.fn()} />);
    const find = screen.getByRole("searchbox", { name: /Find a case by id/ });
    await userEvent.type(find, "7d44");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await userEvent.clear(find);
    await userEvent.click(screen.getByRole("button", { name: "Show case details..." }));
    await screen.findByText("KT-2026-1");
    await userEvent.type(screen.getByRole("searchbox", { name: /reference or id/ }), "kt-2026-2");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("KT-2026-2");
    await userEvent.type(screen.getByRole("searchbox", { name: /reference or id/ }), "9");
    expect(screen.getByText(/No case matches/)).toBeInTheDocument();
  });

  it("lists only the cases past their retention date when asked", async () => {
    routes({ store_overview: () => OVERVIEW });
    render(<StoreScreen store={STORE} notice={null} onStore={vi.fn()} onOpened={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Show case details..." }));
    await screen.findByText("KT-2026-1");
    await userEvent.click(screen.getByRole("checkbox", { name: /Only cases past their retention date/ }));
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("KT-2026-2");
  });

  it("exports a key card for the laboratory's register", async () => {
    const mocked = routes({
      export_key_card: () => ({ key_id: "0123456789abcdef", holder: "Examiner A", exported: "D:/card.json" }),
    });
    render(<StoreScreen store={STORE} notice={null} onStore={vi.fn()} onOpened={vi.fn()} />);
    await userEvent.click(screen.getByText("Register this key with the laboratory"));
    await userEvent.type(screen.getByRole("textbox", { name: /Your name/ }), "Examiner A");
    await userEvent.click(screen.getByRole("button", { name: "Export key card..." }));
    expect(await screen.findByText(/Key card for key 0123456789abcdef saved/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("export_key_card", { request: { holder: "Examiner A" } });
  });

  it("backs up the store to a new folder", async () => {
    const mocked = routes({ backup_store: () => ({ exported: "E:/backup", files: 12, bytes: 4096 }) });
    render(<StoreScreen store={STORE} notice={null} onStore={vi.fn()} onOpened={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Back up this store..." }));
    expect(await screen.findByText(/Backup written: 12 encrypted file\(s\)/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("backup_store", {});
  });
});
