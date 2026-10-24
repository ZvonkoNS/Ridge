// Capture check (FR-54): whether photographing the finger again would help, on a photo chosen before
// import (read once, never changed) or on a stored photo (a logged read). Indicative only: it is not a
// quality score of a print and says nothing about identification.
import { useState } from "react";

import { IpcError, ipc } from "../ipc/commands";
import type { CaptureCheck, CaptureFinding } from "../ipc/types";
import { Button } from "./ui";

const LEVEL_TEXT: Record<CaptureFinding["level"], string> = {
  ok: "OK",
  retake: "Retake",
  note: "Note",
};
const LEVEL_CLASS: Record<CaptureFinding["level"], string> = {
  ok: "badge badge-ok",
  retake: "badge badge-problem",
  note: "badge badge-hold",
};

/** The measured values in one line, for the examiner who wants the numbers behind the findings. */
export function measuredLine(check: CaptureCheck): string {
  const parts = [`${check.width} × ${check.height} px`];
  parts.push(
    check.finger_located
      ? `finger ${(100 * check.finger_share).toFixed(0)} % of the frame`
      : "finger not located",
  );
  if (check.ridge_spacing_px != null) {
    parts.push(`${check.ridge_spacing_px.toFixed(1)} px per ridge`);
  }
  if (check.clarity != null) {
    parts.push(`peak share ${check.clarity.toFixed(2)}`);
  }
  if (check.glare_share != null) {
    parts.push(`glare ${(100 * check.glare_share).toFixed(0)} %`);
  }
  return parts.join(" · ");
}

/** The verdict, the findings with their levels, the measured values and the notice of one capture check. */
export function CaptureFindings({ check }: { check: CaptureCheck }) {
  const verdict =
    check.verdict === "retake"
      ? "Photograph the finger again if you still can."
      : "No reason to photograph the finger again was found.";
  return (
    <div className="capture-findings" aria-live="polite">
      <p className={check.verdict === "retake" ? "capture-verdict capture-retake" : "capture-verdict"}>
        <strong>{verdict}</strong>
      </p>
      <ul className="findings">
        {check.findings.map((f) => (
          <li key={f.id}>
            <span className={LEVEL_CLASS[f.level]}>{LEVEL_TEXT[f.level]}</span> {f.text}
          </li>
        ))}
      </ul>
      <p className="muted">{measuredLine(check)}</p>
      <p className="muted">{check.notice}</p>
    </div>
  );
}

interface Props {
  /** A stored photo to check (its read is logged), or null to choose a file before import. */
  sha256: string | null;
  onFailure: (error: unknown) => void;
}

/** A card with the button that runs the check (a file dialog before import, or a stored photo) and its findings. */
export function CaptureCheckCard({ sha256, onFailure }: Props) {
  const [check, setCheck] = useState<CaptureCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      setCheck(sha256 === null ? await ipc.checkPhoto() : await ipc.checkEvidence(sha256));
    } catch (error) {
      if (error instanceof IpcError && error.kind === "cancelled") {
        return; // the file dialog was closed: nothing was checked
      }
      onFailure(error);
    } finally {
      setBusy(false);
    }
  };
  const title = sha256 === null ? "Check a photo before import" : "Capture check of this photo";
  return (
    <section className="card capture-check" aria-label={title}>
      <h3>{title}</h3>
      <p className="muted">
        Says whether photographing the finger again would help: finger located and large enough, pixels per
        ridge, clarity, glare, and whether the file is the camera&apos;s original. Not a quality score.
        {sha256 === null ? " The file is read once and never changed." : " The read is logged."}
      </p>
      <Button
        onClick={() => {
          void run();
        }}
        busy={busy}
      >
        {sha256 === null ? "Check a photo..." : "Check this photo"}
      </Button>
      {check ? <CaptureFindings check={check} /> : null}
    </section>
  );
}
