import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Item } from "../ipc/types";
import { ReviewPanel } from "../screens/ReviewPanel";
import { ipcError, routes } from "./ipc";

function photo(n: number): Item {
  return {
    sha256: String(n).repeat(64),
    role: "evidence",
    size: 10,
    label: `IMG_${n}.jpg`,
    job_id: null,
    source: null,
  };
}

const PREVIEW = {
  sha256: "",
  width: 100,
  height: 80,
  source_width: 100,
  source_height: 80,
  ppi: null,
  png_base64: "",
};

describe("run on all photos", () => {
  it("runs one job per photo with the shared settings and reports refusals", async () => {
    const photos = [photo(1), photo(2), photo(3)];
    const seen: Record<string, unknown>[] = [];
    routes({
      preview: () => PREVIEW,
      run_job: (request) => {
        seen.push(request ?? {});
        if (request?.evidence === photos[1]?.sha256) {
          return ipcError("refused", "no ridge pattern found");
        }
        return {
          job_id: "j",
          outputs: [],
          measurements: null,
          export: null,
          quality: null,
          minutiae: null,
          limits_of_use: null,
        };
      },
    });
    const notify = vi.fn();
    const onJobDone = vi.fn();
    render(
      <ReviewPanel
        evidence={photos[0] ?? photo(9)}
        allEvidence={photos}
        onFailure={vi.fn()}
        onJobDone={onJobDone}
        notify={notify}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Run on all 3 photos" }));
    await waitFor(() => {
      expect(notify).toHaveBeenCalled();
    });
    expect(seen.map((r) => r.evidence)).toEqual(photos.map((p) => p.sha256));
    expect(seen.every((r) => r.roi === null && r.ruler === null)).toBe(true);
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("2 of 3 jobs done"));
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("IMG_2.jpg: no ridge pattern found"));
    expect(onJobDone).toHaveBeenCalled();
  });

  it("is not offered for a single photo", () => {
    routes({ preview: () => PREVIEW });
    render(
      <ReviewPanel evidence={photo(1)} allEvidence={[photo(1)]} onFailure={vi.fn()} onJobDone={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /Run on all/ })).toBeNull();
  });
});
