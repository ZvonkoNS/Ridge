import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EvidenceSection } from "../screens/EvidenceSection";
import { routes } from "./ipc";

const item = (n: number) => ({
  sha256: String(n).repeat(64).slice(0, 64),
  role: "evidence" as const,
  size: 1000,
  label: `IMG_00${n}.jpg`,
  job_id: null,
  source: "Exhibit 12",
});

describe("evidence import", () => {
  it("imports several photos and names the ones that were refused", async () => {
    const mocked = routes({
      import_evidence: () => ({
        imported: [item(1), item(2)],
        refused: [{ name: "notes.pdf", message: "not a supported image format" }],
      }),
    });
    const onFailure = vi.fn();
    const onChanged = vi.fn();
    render(<EvidenceSection items={[]} onFailure={onFailure} onChanged={onChanged} notify={vi.fn()} />);
    await userEvent.type(screen.getByRole("textbox"), "Exhibit 12");
    await userEvent.click(screen.getByRole("button", { name: "Import photos..." }));
    await waitFor(() => {
      expect(onFailure).toHaveBeenCalled();
    });
    const shown = (onFailure.mock.calls[0]?.[0] as Error).message;
    expect(shown).toContain("Imported 2 photos");
    expect(shown).toContain("notes.pdf: not a supported image format");
    expect(onChanged).toHaveBeenCalled();
    expect(mocked).toHaveBeenCalledWith("import_evidence", { request: { source: "Exhibit 12" } });
  });

  it("reports a single import plainly", async () => {
    routes({ import_evidence: () => ({ imported: [item(3)], refused: [] }) });
    const notify = vi.fn();
    render(<EvidenceSection items={[]} onFailure={vi.fn()} onChanged={vi.fn()} notify={notify} />);
    await userEvent.click(screen.getByRole("button", { name: "Import photos..." }));
    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(expect.stringContaining("Imported IMG_003.jpg"));
    });
  });
});
