import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CaptureCheckCard, measuredLine } from "../components/CaptureCheckCard";
import type { CaptureCheck } from "../ipc/types";
import { axeViolations, ipcError, routes } from "./ipc";

const SHA = "a".repeat(64);
const CHECK: CaptureCheck = {
  schema: "ridge.capture-check/1",
  sha256: SHA,
  width: 3024,
  height: 4032,
  finger_located: true,
  finger_share: 0.31,
  ridge_spacing_px: 11.4,
  clarity: 0.047,
  glare_share: 0.08,
  verdict: "retake",
  findings: [
    { id: "located", level: "ok", text: "The finger fills 31 % of the frame." },
    { id: "glare", level: "retake", text: "Glare covers 8 % of the finger: move the light." },
    { id: "scale", level: "note", text: "Ridge cannot see whether a ruler lies in the plane of the pad." },
  ],
  notice: "This check only says whether photographing the finger again would help.",
};

describe("capture check", () => {
  it("checks a photo before import and lists the findings with their levels", async () => {
    const mocked = routes({ check_photo: () => CHECK });
    const { container } = render(<CaptureCheckCard sha256={null} onFailure={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Check a photo..." }));
    expect(await screen.findByText("Photograph the finger again if you still can.")).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("check_photo", {});
    expect(screen.getByText("Retake")).toHaveClass("badge-problem");
    expect(screen.getByText("OK")).toHaveClass("badge-ok");
    expect(screen.getByText("Note")).toHaveClass("badge-hold");
    expect(screen.getByText(/Glare covers 8 %/)).toBeInTheDocument();
    expect(screen.getByText(CHECK.notice)).toBeInTheDocument();
    expect(screen.getByText(measuredLine(CHECK))).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("checks a stored photo by its hash and says nothing when the dialog is cancelled", async () => {
    const onFailure = vi.fn();
    const mocked = routes({
      check_evidence: (request) => ({
        ...CHECK,
        sha256: String(request?.sha256),
        verdict: "ok",
        findings: [],
      }),
      check_photo: () => ipcError("cancelled", "closed"),
    });
    render(<CaptureCheckCard sha256={SHA} onFailure={onFailure} />);
    await userEvent.click(screen.getByRole("button", { name: "Check this photo" }));
    expect(
      await screen.findByText("No reason to photograph the finger again was found."),
    ).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("check_evidence", { request: { sha256: SHA } });
    render(<CaptureCheckCard sha256={null} onFailure={onFailure} />);
    await userEvent.click(screen.getByRole("button", { name: "Check a photo..." }));
    expect(onFailure).not.toHaveBeenCalled();
  });

  it("words the measured line for an unlocated finger", () => {
    const line = measuredLine({
      ...CHECK,
      finger_located: false,
      finger_share: 1,
      ridge_spacing_px: null,
      clarity: null,
      glare_share: null,
    });
    expect(line).toBe("3024 × 4032 px · finger not located");
  });
});
