import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { exportLine, ScaleNotice } from "../screens/JobSummary";
import { DEFAULT_PARAMS, NO_REFERENCE_HINT, ParametersForm } from "../screens/ParametersForm";
import { photoScale } from "../screens/ReviewPanel";

describe("scale reference (FR-31)", () => {
  it("asks for a ruler or a card while no two points are placed, and proceeds without one", () => {
    const { rerender } = render(
      <ParametersForm value={DEFAULT_PARAMS} onChange={vi.fn()} disabled={false} />,
    );
    expect(screen.getByRole("note")).toHaveTextContent(NO_REFERENCE_HINT);
    expect(screen.getByRole("note")).toHaveTextContent("otherwise proceed as is");
    rerender(
      <ParametersForm
        value={{
          ...DEFAULT_PARAMS,
          ruler: [
            { x: 0, y: 0 },
            { x: 856, y: 0 },
          ],
          reference: "id1-long",
        }}
        onChange={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.getByRole("combobox")).toHaveValue("id1-long");
    expect(screen.getByLabelText("mm")).toBeDisabled();
    expect(screen.getByLabelText("mm")).toHaveValue("85.6");
  });

  it("scales a card by its standard edge with the wider uncertainty", () => {
    const params = {
      ...DEFAULT_PARAMS,
      reference: "id1-long" as const,
      ruler: [
        { x: 0, y: 0 },
        { x: 856, y: 0 },
      ],
    };
    const scale = photoScale(params, null);
    expect(scale?.method).toBe("card");
    expect(scale?.pxPerMm).toBeCloseTo(10, 6);
    expect(scale?.uncertaintyPct).toBeCloseTo(200 / 856 + 0.15 + 2, 6);
    const ruler = photoScale({ ...params, reference: "ruler", rulerMm: "85.6" }, null);
    expect(ruler?.method).toBe("ruler");
    expect(ruler?.uncertaintyPct).toBeCloseTo(200 / 856, 6);
  });

  it("shows the report's scale notice only when no reference was given", () => {
    const estimated = {
      produced: true as const,
      sha256: "a".repeat(64),
      ppi: 500,
      factor: 1,
      transforms: ["polarity:dark-ridges", "scale:500ppi:ridge-period"],
      scale: {
        method: "ridge-period" as const,
        px_per_mm: 20,
        uncertainty_pct: 15,
        notice: "No scale reference was given: proceed as is.",
      },
    };
    render(<ScaleNotice exp={estimated} />);
    expect(screen.getByRole("status")).toHaveTextContent("No scale reference was given: proceed as is.");
    const card = {
      ...estimated,
      scale: {
        method: "card" as const,
        px_per_mm: 10,
        uncertainty_pct: 2.4,
        reference: "ISO/IEC 7810 ID-1 card, long edge (85.60 mm)",
      },
    };
    expect(exportLine(card)).toContain(
      "card edge in the photo (ISO/IEC 7810 ID-1 card, long edge (85.60 mm))",
    );
    const { container } = render(<ScaleNotice exp={card} />);
    expect(container).toBeEmptyDOMElement();
  });
});
