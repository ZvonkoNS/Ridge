import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExhibitLabel, PROCESSED_LABEL } from "../components/ExhibitLabel";
import { barLength, ScaleBar } from "../components/ScaleBar";

const SHA = "3f9a1c2e".padEnd(64, "0");

describe("exhibit labels", () => {
  it("marks every processed image as not an identification", () => {
    for (const role of ["print", "export", "export-gray", "debug"] as const) {
      const { unmount } = render(<ExhibitLabel role={role} sha256={SHA} zoom={1} />);
      expect(screen.getByText(PROCESSED_LABEL)).toBeInTheDocument();
      unmount();
    }
  });

  it("shows the original's hash without the processed warning", () => {
    render(<ExhibitLabel role="evidence" sha256={SHA} zoom={1} />);
    expect(screen.queryByText(PROCESSED_LABEL)).toBeNull();
    expect(screen.getByTitle(`SHA-256 ${SHA}`)).toHaveTextContent("3f9a1c2e0000");
    expect(screen.getByText("Scale unknown")).toBeInTheDocument();
  });
});

describe("scale bar", () => {
  it("chooses a round length that fits on screen", () => {
    expect(barLength(19.685)).toBe(10); // 500 ppi at 100 %
    expect(barLength(100)).toBe(2);
    expect(barLength(1)).toBe(50);
    expect(barLength(1000)).toBe(1);
  });

  it("draws true size at the current zoom and states method and uncertainty", () => {
    render(<ScaleBar source={{ pxPerMm: 500 / 25.4, method: "ruler", uncertaintyPct: 0.25 }} zoom={0.5} />);
    const figure = screen.getByRole("figure");
    expect(figure).toHaveAccessibleName("Scale bar: 20 mm, ruler, ±0.25 %");
    const expected = Math.round(20 * (500 / 25.4) * 0.5) + 2;
    expect(figure.querySelector("svg")?.getAttribute("width")).toBe(String(expected));
  });

  it("names the ridge-period estimate as an estimate", () => {
    render(<ScaleBar source={{ pxPerMm: 20, method: "ridge-period", uncertaintyPct: 15 }} zoom={1} />);
    expect(screen.getByText(/ridge-period estimate, ±15 %/)).toBeInTheDocument();
  });
});
