import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { areaLine } from "../components/PrintArea";
import type { Item, JobResult, PrintArea } from "../ipc/types";
import { ReviewPanel } from "../screens/ReviewPanel";
import { axeViolations, routes } from "./ipc";

const PHOTO: Item = {
  sha256: "e".repeat(64),
  role: "evidence",
  size: 10,
  label: "IMG_1.jpg",
  job_id: null,
  source: null,
};

const PREVIEW = { sha256: "", width: 100, height: 80, source_width: 400, source_height: 320, png_base64: "" };

const AREA: PrintArea = {
  box_px: [100, 60, 180, 200],
  outline_px: [
    [
      [110, 70],
      [270, 70],
      [190, 250],
    ],
  ],
  parts: 1,
};

function job(area: PrintArea | undefined): JobResult {
  return {
    job_id: "1a2b3c4d-0000-4000-8000-000000000000",
    outputs: [
      {
        sha256: "p".repeat(64),
        role: "print",
        size: 5,
        label: "IMG_1_fingerprint.png",
        job_id: "j",
        source: null,
      },
    ],
    measurements: {
      ridge_period_px: 9,
      found_finger: true,
      output_scale: 1,
      ...(area ? { print_area: area } : {}),
    },
    export: {
      produced: true,
      sha256: "x".repeat(64),
      ppi: 500,
      factor: 1,
      transforms: ["polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ridge-period"],
      scale: { method: "ridge-period", px_per_mm: 20, uncertainty_pct: 15 },
    },
    quality: null,
    minutiae: null,
    limits_of_use: null,
  };
}

async function runJob(result: JobResult) {
  routes({ preview: () => PREVIEW, run_job: () => result });
  const view = render(<ReviewPanel evidence={PHOTO} onFailure={vi.fn()} onJobDone={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Run job" }));
  await screen.findByText("Job");
  const original = screen.getByRole("region", { name: "Original photo" });
  await waitFor(() => {
    expect(original.querySelector("svg.viewer-overlay")).not.toBeNull();
  });
  return { ...view, original };
}

describe("where the print was extracted", () => {
  it("outlines the job's print area on the original photo, with its frame and the rest dimmed", async () => {
    const { original } = await runJob(job(AREA));
    const edge = original.querySelector(".ov-area-edge");
    expect(edge?.getAttribute("points")).toBe("110.5,70.5 270.5,70.5 190.5,250.5"); // pixel centres
    const frame = original.querySelector(".ov-area-frame");
    expect([frame?.getAttribute("x"), frame?.getAttribute("y")]).toEqual(["100", "60"]);
    expect([frame?.getAttribute("width"), frame?.getAttribute("height")]).toEqual(["180", "200"]);
    expect(original.querySelector(".ov-area-dim")?.getAttribute("d")).toMatch(/^M0 0H400V320H0Z/);
    expect(screen.getByText(/The comparison export shows this area mirrored/)).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Job result" });
    expect(within(summary).getByText("x 100, y 60, 180 × 200 px of the photo")).toBeInTheDocument();
  });

  it("can be hidden without touching the photo", async () => {
    const { original, container } = await runJob(job(AREA));
    const toggle = screen.getByRole("checkbox", {
      name: /Show where the print was extracted \(job 1a2b3c4d\)/,
    });
    expect(toggle).toBeChecked();
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(toggle);
    expect(original.querySelector(".ov-area")).toBeNull();
    expect(screen.queryByText(/Solid line: the area kept as the print/)).toBeNull();
    expect(within(original).getByRole("img", { name: "Original photo" })).toBeInTheDocument();
  });

  it("says nothing is recorded for a report made before Ridge recorded the area", async () => {
    const { original } = await runJob(job(undefined));
    expect(original.querySelector(".ov-area")).toBeNull();
    expect(screen.queryByRole("checkbox", { name: /Show where the print/ })).toBeNull();
    expect(screen.getByText("not recorded (report made before Ridge recorded it)")).toBeInTheDocument();
  });

  it("names separate kept areas in the summary line", () => {
    expect(areaLine({ ...AREA, parts: 2 })).toBe("x 100, y 60, 180 × 200 px of the photo; 2 kept areas");
    expect(areaLine(null)).toMatch(/^not recorded/);
  });
});
