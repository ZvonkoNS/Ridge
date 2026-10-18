import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ImageViewer } from "../components/ImageViewer";

const props = {
  title: "Original photo",
  url: "blob:test/photo",
  bitmap: { width: 1000, height: 750 },
  source: { width: 4000, height: 3000 },
  label: (zoom: number) => <span data-testid="zoom">{zoom}</span>,
};

function readout(): string {
  return screen.getByRole("status").textContent;
}

describe("image viewer", () => {
  it("is operable from the keyboard and states zoom and interpolation", () => {
    render(<ImageViewer {...props} />);
    const table = screen.getByRole("application");
    table.focus();
    fireEvent.keyDown(table, { key: "1" });
    expect(readout()).toContain("100 %");
    expect(readout()).toContain("nearest neighbour"); // the 1000 px preview is magnified 4x
    fireEvent.keyDown(table, { key: "+" });
    expect(readout()).toContain("150 %");
    fireEvent.keyDown(table, { key: "0" });
    expect(readout()).not.toContain("150 %");
    expect(screen.getByRole("img", { name: "Original photo" })).toHaveAttribute("src", "blob:test/photo");
  });

  it("uses nearest neighbour for magnified pixels and smoothing below", () => {
    render(<ImageViewer {...props} bitmap={{ width: 4000, height: 3000 }} />);
    const table = screen.getByRole("application");
    fireEvent.keyDown(table, { key: "0" });
    expect(readout()).toContain("smoothed");
    expect(screen.getByRole("img", { name: "Original photo" })).not.toHaveClass("px");
    fireEvent.keyDown(table, { key: "1" });
    fireEvent.keyDown(table, { key: "+" });
    expect(screen.getByRole("img", { name: "Original photo" })).toHaveClass("px");
  });

  it("places ruler points in photo pixels", () => {
    const onRulerPoint = vi.fn();
    render(<ImageViewer {...props} tool="ruler" onRulerPoint={onRulerPoint} />);
    const table = screen.getByRole("application");
    fireEvent.keyDown(table, { key: "1" }); // 1 screen px = 1 photo px, image centred in 800 x 600
    table.setPointerCapture = vi.fn();
    fireEvent.pointerDown(table, { button: 0, clientX: 400, clientY: 300, pointerId: 1 });
    fireEvent.pointerUp(table, { button: 0, clientX: 400, clientY: 300, pointerId: 1 });
    expect(onRulerPoint).toHaveBeenCalledWith({ x: 2000, y: 1500 });
  });

  it("offers full resolution only when the preview is magnified", () => {
    const loadDetail = vi.fn();
    render(<ImageViewer {...props} loadDetail={loadDetail} />);
    const table = screen.getByRole("application");
    fireEvent.keyDown(table, { key: "0" });
    expect(screen.queryByRole("button", { name: "Full resolution here" })).toBeNull();
    fireEvent.keyDown(table, { key: "1" });
    expect(screen.getByRole("button", { name: "Full resolution here" })).toBeInTheDocument();
  });
});
