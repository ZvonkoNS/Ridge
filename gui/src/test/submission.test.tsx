import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SubmissionRecord } from "../ipc/types";
import { submissionLine } from "../screens/JobSummary";
import { DEFAULT_PARAMS, FINGER_POSITIONS, ParametersForm } from "../screens/ParametersForm";

const RECORD: SubmissionRecord = {
  finger_position: 2,
  finger: "right index",
  source_agency: "Police of Synthetica",
  impression: "photograph of a finger (contactless), ridge image processed by Ridge",
  capture_device: "Synthetic Camera Co Model 7",
  capture_device_note: "as the photo's file records it; not verified by Ridge",
  notice:
    "Finger position and source agency are the examiner's statements; nothing here is an identification.",
};

describe("submission record (FR-38)", () => {
  it("offers the eleven finger codes and a source agency field", () => {
    render(<ParametersForm value={DEFAULT_PARAMS} onChange={vi.fn()} disabled={false} />);
    expect(FINGER_POSITIONS).toHaveLength(11);
    const finger = screen.getByLabelText("Finger shown");
    expect(finger).toHaveValue("0");
    expect(screen.getByRole("option", { name: "7: left index" })).toBeInTheDocument();
    expect(screen.getByLabelText("Source agency")).toHaveAttribute("placeholder", "not stated");
  });

  it("states the record as the examiner's and the camera as unverified", () => {
    expect(submissionLine(RECORD)).toBe(
      "finger position 2 (right index); source agency Police of Synthetica; capture device Synthetic Camera Co Model 7 (as the photo's file records it; not verified by Ridge)",
    );
    expect(submissionLine({ ...RECORD, source_agency: null, capture_device: null })).toContain(
      "source agency not stated; capture device none named in the file",
    );
    expect(submissionLine(null)).toBeNull();
  });
});
