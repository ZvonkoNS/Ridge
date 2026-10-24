import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Item, JobResult } from "../ipc/types";
import { ReviewPanel } from "../screens/ReviewPanel";
import { routes } from "./ipc";

const PHOTO: Item = {
  sha256: "e".repeat(64),
  role: "evidence",
  size: 10,
  label: "IMG_1.jpg",
  job_id: null,
  source: null,
};
const PREVIEW = { sha256: "", width: 100, height: 80, source_width: 400, source_height: 320, png_base64: "" };

function job(uncertainty: number): JobResult {
  return {
    job_id: "1a2b3c4d-0000-4000-8000-000000000000",
    outputs: [
      {
        sha256: "g".repeat(64),
        role: "export-gray",
        size: 5,
        label: "IMG_1_comparison_gray_500ppi.png",
        job_id: "j",
        source: null,
      },
    ],
    measurements: { ridge_period_px: 9, found_finger: true, output_scale: 1 },
    export: {
      produced: true,
      sha256: "x".repeat(64),
      ppi: 500,
      factor: 1,
      transforms: ["polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ridge-period"],
      scale: { method: "ridge-period", px_per_mm: 20, uncertainty_pct: uncertainty },
    },
    quality: null,
    minutiae: null,
    limits_of_use: null,
  };
}

describe("scale sweep (FR-39)", () => {
  it("offers a sweep for an export with an uncertain scale and names the written files", async () => {
    const notify = vi.fn();
    const mocked = routes({
      preview: () => PREVIEW,
      run_job: () => job(15),
      export_sweep: () => ({
        exported: "D:/sweep",
        files: 3,
        factors: [0.85, 1, 1.15],
        index: "SWEEP.csv",
        uncertainty_pct: 15,
      }),
    });
    render(<ReviewPanel evidence={PHOTO} onFailure={vi.fn()} onJobDone={vi.fn()} notify={notify} />);
    expect(screen.queryByRole("button", { name: "Export scale sweep..." })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Run job" }));
    await userEvent.click(await screen.findByRole("button", { name: "Export scale sweep..." }));
    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(expect.stringContaining("0.8500, 1.0000, 1.1500"));
    });
    expect(mocked).toHaveBeenCalledWith("export_sweep", {
      request: { sha256: "g".repeat(64), steps: 3, format: "png" },
    });
  });

  it("is not offered when the scale is exact", async () => {
    routes({ preview: () => PREVIEW, run_job: () => job(0) });
    render(<ReviewPanel evidence={PHOTO} onFailure={vi.fn()} onJobDone={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Run job" }));
    await screen.findByText(/Job/);
    expect(screen.queryByRole("button", { name: "Export scale sweep..." })).toBeNull();
  });
});
