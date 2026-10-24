import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ImageViewer } from "../components/ImageViewer";

const props = {
  title: "Original photo",
  url: "blob:test/photo",
  bitmap: { width: 4000, height: 3000 },
  source: { width: 4000, height: 3000 },
  label: () => null,
};

describe("linked image viewers", () => {
  it("puts the given focus at the centre and reports pans and zooms as a new focus", () => {
    const onFocus = vi.fn();
    const onZoom = vi.fn();
    const { container } = render(
      <ImageViewer {...props} zoom={1} focus={{ x: 2000, y: 1500 }} onFocus={onFocus} onZoom={onZoom} />,
    );
    const stage = container.querySelector<HTMLElement>(".viewer-stage");
    expect(stage?.style.transform).toBe("translate(-1600px, -1200px)"); // the viewer is 800 x 600 here
    const table = screen.getByRole("application");
    fireEvent.keyDown(table, { key: "ArrowLeft" }); // the image moves right by 48 px: the centre pixel is 48 px further left
    expect(onFocus).toHaveBeenLastCalledWith({ x: 1952, y: 1500 });
    fireEvent.keyDown(table, { key: "+" }); // zooming around the centre keeps the focus
    expect(onZoom).toHaveBeenLastCalledWith(1.5);
    expect(onFocus).toHaveBeenLastCalledWith({ x: 2000, y: 1500 });
    fireEvent.keyDown(table, { key: "0" }); // fit: the focus is the image's centre
    expect(onFocus).toHaveBeenLastCalledWith({ x: 2000, y: 1500 });
  });

  it("reports a mark in whole image pixels only with the mark tool", () => {
    const onMark = vi.fn();
    const { rerender } = render(<ImageViewer {...props} tool="pan" onMark={onMark} />);
    const table = screen.getByRole("application");
    table.setPointerCapture = vi.fn();
    fireEvent.keyDown(table, { key: "1" });
    fireEvent.pointerDown(table, { button: 0, clientX: 400.6, clientY: 300.4, pointerId: 1 });
    fireEvent.pointerUp(table, { button: 0, clientX: 400.6, clientY: 300.4, pointerId: 1 });
    expect(onMark).not.toHaveBeenCalled();
    rerender(<ImageViewer {...props} tool="mark" onMark={onMark} />);
    fireEvent.pointerDown(table, { button: 0, clientX: 400.6, clientY: 300.4, pointerId: 1 });
    fireEvent.pointerUp(table, { button: 0, clientX: 400.6, clientY: 300.4, pointerId: 1 });
    expect(onMark).toHaveBeenCalledWith({ x: 2000, y: 1500 });
    fireEvent.keyDown(table, { key: "0" }); // fitted: the image leaves a grey margin
    fireEvent.pointerDown(table, { button: 0, clientX: 2, clientY: 2, pointerId: 1 });
    fireEvent.pointerUp(table, { button: 0, clientX: 2, clientY: 2, pointerId: 1 });
    expect(onMark).toHaveBeenCalledTimes(1); // the grey margin is not a pixel of the image
  });
});
