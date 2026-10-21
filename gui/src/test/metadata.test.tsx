import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PhotoMetadataPanel, StoredPhotoMetadata } from "../components/PhotoMetadata";
import type { Item, PhotoMetadata } from "../ipc/types";
import { ReviewPanel } from "../screens/ReviewPanel";
import { axeViolations, ipcError, routes } from "./ipc";

const MAP_URL = "https://www.google.com/maps/search/?api=1&query=46.0512333%2C14.5056778";

const META: PhotoMetadata = {
  schema: "ridge.photo-metadata/1",
  notice: "Read from the file as stored. Ridge does not verify metadata.",
  summary: [{ name: "Camera", id: "EXIF Make, Model", value: "Synthetic Camera Co Model 7" }],
  location: {
    source: "EXIF GPS",
    latitude: 46.0512333,
    longitude: 14.5056778,
    recorded: "46° 3' 4.44\" N, 14° 30' 20.44\" E",
    map_url: MAP_URL,
    altitude_m: 295.3,
    time_utc: "2024-05-01T08:22:33.5Z",
  },
  groups: [
    {
      id: "exif-ifd0",
      title: "EXIF: image (IFD0)",
      entries: [
        { name: "Make", id: "0x010F", value: "Synthetic Camera Co" },
        { name: "Software", id: "0x0131", value: "Firmware 1.2" },
      ],
    },
    { id: "xmp", title: "XMP", entries: [{ name: "xmp:CreatorTool", value: "Synthetic Editor 3" }] },
  ],
  embedded: [
    {
      kind: "EXIF thumbnail",
      format: "JPEG",
      size_px: [16, 12],
      bytes: 631,
      sha256: "sha256:" + "a".repeat(64),
    },
  ],
  warnings: ["The camera maker's MakerNote is vendor-specific and was not decoded."],
  entries: 4,
  truncated: false,
};

const PHOTO: Item = {
  sha256: "e".repeat(64),
  role: "evidence",
  size: 10,
  label: "IMG_1.jpg",
  job_id: null,
  source: null,
};

function clipboard(writeText: (text: string) => Promise<void>): void {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

describe("photo metadata panel", () => {
  it("shows the position with a Google Maps link to copy, never to open", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    clipboard(writeText);
    const { container } = render(<PhotoMetadataPanel metadata={META} />);
    const panel = screen.getByRole("region", { name: "Photo metadata" });
    expect(within(panel).getByText("46.0512333, 14.5056778")).toBeInTheDocument();
    expect(within(panel).getByText(MAP_URL)).toBeInTheDocument();
    expect(within(panel).getByText(/Ridge does not open links/)).toBeInTheDocument();
    expect(container.querySelector("a[href]")).toBeNull(); // nothing in the WebView navigates away
    await userEvent.click(within(panel).getByRole("button", { name: "Copy Google Maps link" }));
    expect(writeText).toHaveBeenCalledWith(MAP_URL);
    await userEvent.click(within(panel).getByRole("button", { name: "Copy coordinates" }));
    expect(writeText).toHaveBeenLastCalledWith("46.0512333, 14.5056778");
    expect(within(panel).getByText("295.3 m")).toBeInTheDocument();
    expect(within(panel).getByText("2024-05-01T08:22:33.5Z")).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("lists every group with its tags, and finds entries across groups", async () => {
    render(<PhotoMetadataPanel metadata={META} />);
    const ifd0 = screen.getByText("EXIF: image (IFD0)", { selector: "summary" }).closest("details");
    expect(ifd0).not.toBeNull();
    expect(ifd0?.open).toBe(false);
    expect(within(ifd0 as HTMLElement).getByText("0x010F")).toBeInTheDocument();
    expect(within(ifd0 as HTMLElement).getByText("Synthetic Camera Co")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "Find in metadata" }), "editor");
    expect(screen.queryByText("EXIF: image (IFD0)", { selector: "summary" })).toBeNull();
    const xmp = screen.getByText("XMP", { selector: "summary" }).closest("details");
    expect(xmp?.open).toBe(true);
    expect(within(xmp as HTMLElement).getByText("Synthetic Editor 3")).toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox", { name: "Find in metadata" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Find in metadata" }), "nothing like this");
    expect(screen.getByText('No entry contains "nothing like this".')).toBeInTheDocument();
  });

  it("shows embedded images by hash only, and the notes on reading", () => {
    render(<PhotoMetadataPanel metadata={META} />);
    expect(screen.getByText(/EXIF thumbnail, JPEG 16 × 12 px, 631 bytes/)).toBeInTheDocument();
    expect(screen.getByText(/Ridge does not show them/)).toBeInTheDocument();
    expect(screen.getByText(/MakerNote is vendor-specific/)).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("says when no position is recorded", () => {
    render(<PhotoMetadataPanel metadata={{ ...META, location: null }} />);
    expect(screen.getByText("No position is recorded in this photo's metadata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy Google Maps link" })).toBeNull();
  });

  it("shows a report's recorded metadata, or says an older report has none", () => {
    const { rerender } = render(<PhotoMetadataPanel metadata={META} from="report" />);
    expect(
      screen.getByRole("region", { name: "Photo metadata (as recorded in this report)" }),
    ).toBeInTheDocument();
    rerender(<PhotoMetadataPanel metadata={undefined} from="report" />);
    expect(screen.getByText(/Not recorded in this report/)).toBeInTheDocument();
  });

  it("reads a stored photo's metadata once, and reports a failure", async () => {
    const calls = routes({
      photo_metadata: () => ({ sha256: PHOTO.sha256, role: "evidence", metadata: META }),
    });
    render(<StoredPhotoMetadata sha256={PHOTO.sha256} onFailure={vi.fn()} />);
    expect(screen.getByText("Reading the photo's metadata...")).toBeInTheDocument();
    expect(await screen.findByText(MAP_URL)).toBeInTheDocument();
    expect(calls).toHaveBeenCalledWith("photo_metadata", { request: { sha256: PHOTO.sha256 } });
    expect(calls).toHaveBeenCalledTimes(1);

    const onFailure = vi.fn();
    routes({ photo_metadata: () => ipcError("refused", "metadata is shown for imported photos only") });
    render(<StoredPhotoMetadata sha256={"f".repeat(64)} onFailure={onFailure} />);
    expect(await screen.findByText("The metadata could not be read.")).toBeInTheDocument();
    expect(onFailure).toHaveBeenCalledOnce();
  });

  it("appears under the photos in the review, before the job settings", async () => {
    routes({
      preview: () => ({
        sha256: "",
        width: 100,
        height: 80,
        source_width: 400,
        source_height: 320,
        png_base64: "",
      }),
      photo_metadata: () => ({ sha256: PHOTO.sha256, role: "evidence", metadata: META }),
    });
    const { container } = render(<ReviewPanel evidence={PHOTO} onFailure={vi.fn()} onJobDone={vi.fn()} />);
    const panel = await screen.findByRole("region", { name: "Photo metadata" });
    await waitFor(() => {
      expect(within(panel).getByText(MAP_URL)).toBeInTheDocument();
    });
    const pair = container.querySelector(".review-pair");
    const run = screen.getByRole("button", { name: "Run job" });
    expect(pair?.compareDocumentPosition(panel)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(panel.compareDocumentPosition(run)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
