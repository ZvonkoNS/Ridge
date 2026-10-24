import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProvenanceHintsList } from "../components/PhotoMetadata";

const HINTS = {
  schema: "ridge.provenance-hints/1",
  hints: [
    { id: "no-exif", text: "The file carries no EXIF block." },
    { id: "jpeg-quality", text: "Estimated JPEG quality 74 (approximate)." },
  ],
  jpeg_quality_estimate: 74,
  notice: "Hints only. Ridge does not verify them.",
};

describe("provenance hints (FR-42)", () => {
  it("lists the hints with the notice that nothing is verified", () => {
    render(<ProvenanceHintsList hints={HINTS} />);
    expect(screen.getByRole("region", { name: "Provenance hints" })).toBeInTheDocument();
    expect(screen.getByText("Hints only. Ridge does not verify them.")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("says when there is no hint, and renders nothing for older reports", () => {
    const { container, rerender } = render(<ProvenanceHintsList hints={{ ...HINTS, hints: [] }} />);
    expect(screen.getByText(/No hint/)).toBeInTheDocument();
    rerender(<ProvenanceHintsList hints={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
