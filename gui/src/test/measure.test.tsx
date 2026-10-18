import { act, render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MeasureReadout, distanceText, useMeasure } from "../components/Measure";

describe("measuring", () => {
  it("gives millimetres only with a known scale, with its method and uncertainty", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 30, y: 40 },
    ];
    const scale = { pxPerMm: 500 / 25.4, uncertaintyPct: 15, method: "ridge-period" };
    expect(distanceText(points, scale)).toBe("2.54 mm ± 15.0 % (scale: ridge-period estimate) · 50.0 px");
    expect(distanceText(points, null)).toBe("50.0 px (no known scale for this image)");
    expect(distanceText(points.slice(0, 1), scale)).toBeNull();
  });

  it("guides the examiner until two points are placed", () => {
    const { rerender } = render(<MeasureReadout points={[]} scale={null} />);
    expect(screen.getByRole("status")).toHaveTextContent("Click two points");
    rerender(<MeasureReadout points={[{ x: 1, y: 1 }]} scale={null} />);
    expect(screen.getByRole("status")).toHaveTextContent("a second point");
    rerender(
      <MeasureReadout
        points={[
          { x: 0, y: 0 },
          { x: 3, y: 4 },
        ]}
        scale={null}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("nothing is recorded");
  });

  it("keeps two points and starts again on a third click", () => {
    const { result } = renderHook(() => useMeasure());
    expect(result.current.viewer.tool).toBe("pan");
    act(() => {
      result.current.toggle();
    });
    expect(result.current.viewer.tool).toBe("ruler");
    for (const x of [1, 2, 3]) {
      act(() => {
        result.current.viewer.onRulerPoint({ x, y: 0 });
      });
    }
    expect(result.current.points).toEqual([{ x: 3, y: 0 }]);
  });
});
