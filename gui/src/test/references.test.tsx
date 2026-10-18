import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Item } from "../ipc/types";
import { ReferencesSection, scaleFrom } from "../screens/ReferencesSection";
import { axeViolations, routes } from "./ipc";

const EXPORT: Item = {
  sha256: "e".repeat(64),
  role: "export",
  size: 1000,
  label: "finger_comparison_500ppi.png",
  job_id: "j",
  source: null,
};
const REFERENCE: Item = {
  sha256: "f".repeat(64),
  role: "reference",
  size: 1000,
  label: "candidate.png",
  job_id: null,
  source: "NAFIS candidate 1",
};

function preview(ppi: number | null, side: number) {
  return {
    sha256: "",
    width: side,
    height: side,
    source_width: side,
    source_height: side,
    ppi,
    png_base64: "",
  };
}

function bars(): { name: string; width: string | null | undefined }[] {
  return screen.getAllByRole("figure").map((f) => ({
    name: f.getAttribute("aria-label") ?? "",
    width: f.querySelector("svg")?.getAttribute("width"),
  }));
}

describe("equal-scale comparison", () => {
  it("never invents a scale: only declared or typed resolutions count", () => {
    expect(scaleFrom(null, "file")).toBeNull();
    expect(scaleFrom(500, "file")).toEqual({ pxPerMm: 500 / 25.4, method: "file", uncertaintyPct: null });
  });

  it("links both viewers so a millimetre is equally long on screen", async () => {
    routes({
      preview: (request) => (request?.sha256 === EXPORT.sha256 ? preview(500, 400) : preview(1000, 800)),
    });
    const { container } = render(
      <ReferencesSection
        items={[EXPORT, REFERENCE]}
        onFailure={vi.fn()}
        onChanged={vi.fn()}
        notify={vi.fn()}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Ridge export"), EXPORT.sha256);
    await userEvent.selectOptions(screen.getByLabelText("Reference"), REFERENCE.sha256);
    await waitFor(() => {
      expect(bars()).toHaveLength(2);
    });
    expect(bars()[1]?.name).toContain("resolution in the file");
    await userEvent.click(screen.getByLabelText("Equal scale: link the zoom of both images"));
    const [left, right] = bars();
    expect(left?.name.replace("resolution in the file", "")).toBe(
      right?.name.replace("resolution in the file", ""),
    );
    expect(left?.width).toBe(right?.width);
    expect(await axeViolations(container)).toEqual([]);
  });

  it("cannot link without the reference's resolution", async () => {
    routes({
      preview: (request) => (request?.sha256 === EXPORT.sha256 ? preview(500, 400) : preview(null, 800)),
    });
    render(
      <ReferencesSection
        items={[EXPORT, REFERENCE]}
        onFailure={vi.fn()}
        onChanged={vi.fn()}
        notify={vi.fn()}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText("Ridge export"), EXPORT.sha256);
    await userEvent.selectOptions(screen.getByLabelText("Reference"), REFERENCE.sha256);
    expect(await screen.findByText(/Needs the reference's resolution/)).toBeInTheDocument();
    expect(screen.getByLabelText("Equal scale: link the zoom of both images")).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Reference ppi"), "1000");
    expect(screen.getByLabelText("Equal scale: link the zoom of both images")).toBeEnabled();
  });
});
