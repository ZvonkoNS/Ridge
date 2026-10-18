import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ImageViewer } from "../components/ImageViewer";
import type { Item, MinutiaeView } from "../ipc/types";
import { marksFor } from "../lib/minutiae";
import { Inventory, LimitsCard } from "../screens/Inventory";
import { LimitsOutcome } from "../screens/JobSummary";
import { axeViolations, routes } from "./ipc";

const VIEW: MinutiaeView = {
  sha256: "m".repeat(64),
  job_id: null,
  label: "unvalidated",
  print: {
    width: 400,
    height: 500,
    ridge_period_px: 10,
    minutiae: [
      { x: 10, y: 20, type: "ending", angle_deg: 0, quality: 50 },
      { x: 30, y: 40, type: "bifurcation", angle_deg: 90, quality: 50 },
    ],
  },
  export: { width: 200, height: 250, ridge_period_px: 5, minutiae: [] },
};

describe("minutiae overlay", () => {
  it("maps the artefact onto the shown output only when its size matches", () => {
    const marks = marksFor(VIEW, "print", { width: 400, height: 500 });
    expect(marks?.items).toEqual([
      { x: 10, y: 20, kind: "ending", angle: 0 },
      { x: 30, y: 40, kind: "bifurcation", angle: 90 },
    ]);
    expect(marks?.size).toBe(4.5);
    expect(marksFor(VIEW, "export", { width: 200, height: 250 })?.items).toEqual([]);
    expect(marksFor(VIEW, "print", { width: 401, height: 500 })).toBeNull();
    expect(marksFor(VIEW, "debug", { width: 400, height: 500 })).toBeNull();
    expect(marksFor(null, "print", { width: 400, height: 500 })).toBeNull();
  });

  it("draws endings as circles and bifurcations as squares, over unchanged pixels", () => {
    const marks = marksFor(VIEW, "print", { width: 400, height: 500 });
    const { container } = render(
      <ImageViewer
        title="print output"
        url="blob:test/print"
        bitmap={{ width: 400, height: 500 }}
        source={{ width: 400, height: 500 }}
        marks={marks}
        label={() => null}
      />,
    );
    expect(container.querySelectorAll(".ov-ending circle")).toHaveLength(1);
    expect(container.querySelectorAll(".ov-bifurcation rect")).toHaveLength(1);
    const tick = container.querySelector(".ov-bifurcation line");
    expect(Number(tick?.getAttribute("y2"))).toBeLessThan(40); // 90 degrees points up in image space
    expect(screen.getByRole("img", { name: "print output" })).toHaveAttribute("src", "blob:test/print");
  });
});

describe("limits of use", () => {
  it("states a job's outcome without refusing it", async () => {
    const { container, rerender } = render(
      <LimitsOutcome
        section={{
          configured: true,
          source: "VR-2027-01",
          sha256: "a".repeat(64),
          limits: { require_ruler: true },
          within: false,
          warnings: ["the export scale comes from ridge-period; the limits require a ruler in the photo"],
        }}
      />,
    );
    expect(screen.getByText("Outside the limits of use")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent("require a ruler");
    expect(await axeViolations(container)).toEqual([]);
    rerender(<LimitsOutcome section={{ configured: false }} />);
    expect(screen.getByText(/No limits of use are configured/)).toBeInTheDocument();
    rerender(<LimitsOutcome section={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the store's limits and their source", () => {
    render(
      <LimitsCard
        limits={{ configured: true, source: "VR-2027-01", sha256: "b".repeat(64), limits: { min_nfiq2: 30 } }}
      />,
    );
    expect(screen.getByText("VR-2027-01")).toBeInTheDocument();
    expect(screen.getByText("min_nfiq2")).toBeInTheDocument();
  });
});

describe("stored items", () => {
  it("exports any item through the core's save dialog", async () => {
    const items: Item[] = [
      {
        sha256: "c".repeat(64),
        role: "minutiae",
        size: 2048,
        label: "finger_minutiae.json",
        job_id: "j",
        source: null,
      },
    ];
    const mocked = routes({ export_item: () => ({ exported: "D:/out/finger_minutiae.json" }) });
    const notify = vi.fn();
    const { container } = render(
      <Inventory items={items} limits={null} onFailure={vi.fn()} notify={notify} />,
    );
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "Export finger_minutiae.json" }));
    expect(mocked).toHaveBeenCalledWith("export_item", {
      request: { sha256: "c".repeat(64), suggested_name: "finger_minutiae.json" },
    });
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("custody log"));
  });
});
