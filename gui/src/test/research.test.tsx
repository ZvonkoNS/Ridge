import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DEFAULT_PARAMS, ParametersForm, withoutVariants, type Params } from "../screens/ParametersForm";

describe("research mode (ADR-015)", () => {
  it("hides the method variants unless research mode is on", () => {
    const { rerender } = render(
      <ParametersForm value={DEFAULT_PARAMS} onChange={vi.fn()} disabled={false} />,
    );
    expect(screen.queryByText("Method variants (unvalidated, off by default)")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Local ridge frequency/)).not.toBeInTheDocument();
    rerender(<ParametersForm value={DEFAULT_PARAMS} onChange={vi.fn()} disabled={false} research />);
    expect(screen.getByText("Method variants (unvalidated, off by default)")).toBeInTheDocument();
    expect(screen.getByLabelText(/Rectify pad curvature/)).toBeInTheDocument();
  });

  it("puts every variant back to its default when research mode is left", () => {
    const tuned: Params = {
      ...DEFAULT_PARAMS,
      minQuality: 0.3,
      channel: "auto",
      specularMask: true,
      upright: true,
      localFrequency: true,
      rectify: true,
    };
    const reset = withoutVariants(tuned);
    expect(reset.minQuality).toBe(0.3); // the examiner's other settings stay
    expect(reset.channel).toBe("green");
    expect(reset.specularMask).toBe(false);
    expect(reset.upright).toBe(false);
    expect(reset.localFrequency).toBe(false);
    expect(reset.rectify).toBe(false);
    expect(withoutVariants(DEFAULT_PARAMS)).toEqual(DEFAULT_PARAMS);
  });
});
