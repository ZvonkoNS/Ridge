import { describe, expect, it } from "vitest";

import { roleName } from "../components/ExhibitLabel";
import type { ExportInfo, MinutiaeView } from "../ipc/types";
import { marksFor } from "../lib/minutiae";
import { exportLine } from "../screens/JobSummary";

type Produced = Extract<ExportInfo, { produced: true }>;

/** An export as a report made before FR-37 describes it: no grayscale twin. */
const BINARY_ONLY: Produced = {
  produced: true,
  sha256: "a".repeat(64),
  ppi: 500,
  factor: 1,
  transforms: ["polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ruler"],
  scale: { method: "ruler", px_per_mm: 20, uncertainty_pct: 0.5 },
};

const EXPORT: Produced = {
  ...BINARY_ONLY,
  grayscale: {
    sha256: "b".repeat(64),
    transforms: ["tone:grayscale", "polarity:dark-ridges", "mirror:horizontal", "scale:500ppi:ruler"],
  },
};

const VIEW: MinutiaeView = {
  sha256: "c".repeat(64),
  job_id: null,
  label: "finger_minutiae.json",
  print: null,
  export: {
    width: 200,
    height: 250,
    ridge_period_px: 9,
    minutiae: [{ x: 10, y: 20, type: "ending", angle_deg: 30, quality: 80 }],
  },
};

describe("grayscale comparison export (FR-37)", () => {
  it("has its own exhibit name and is named in the export line", () => {
    expect(roleName("export-gray")).toBe("Grayscale comparison export");
    expect(exportLine(EXPORT)).toBe(
      "500 ppi, scale from ruler in the photo, ±0.50 %; polarity:dark-ridges, mirror:horizontal, scale:500ppi:ruler; grayscale twin bbbbbbbbbbbb",
    );
    expect(exportLine(BINARY_ONLY)).not.toContain("grayscale twin");
  });

  it("shares the export-space minutiae with the binary export", () => {
    const shown = { width: 200, height: 250 };
    expect(marksFor(VIEW, "export-gray", shown)?.items).toHaveLength(1);
    expect(marksFor(VIEW, "export", shown)?.items).toHaveLength(1);
    expect(marksFor(VIEW, "print", shown)).toBeNull();
  });
});
