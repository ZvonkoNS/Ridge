// DEVELOPMENT PREVIEW ONLY: synthetic photo metadata for the mocked IPC bridge in preview.ts. The
// values are invented (no real device, person or place); only `npm run dev` ever loads this.
import type { PhotoMetadata } from "../ipc/types";

const NOTICE =
  "Read from the file as stored. Ridge does not verify metadata: any editor can change or remove it, " +
  "so it does not by itself establish where, when or with what the photo was taken.";

export function previewMetadata(withLocation: boolean): PhotoMetadata {
  const gps = withLocation
    ? [
        { name: "GPSLatitudeRef", id: "0x0001", value: "N" },
        { name: "GPSLatitude", id: "0x0002", value: "46, 3, 4.44" },
        { name: "GPSLongitudeRef", id: "0x0003", value: "E" },
        { name: "GPSLongitude", id: "0x0004", value: "14, 30, 20.44" },
        { name: "GPSAltitude", id: "0x0006", value: "295.3" },
      ]
    : [];
  return {
    schema: "ridge.photo-metadata/1",
    notice: NOTICE,
    summary: [
      { name: "Camera", id: "EXIF Make, Model", value: "Synthetic Camera Co Model 7" },
      {
        name: "Taken (camera clock)",
        id: "EXIF DateTimeOriginal, OffsetTimeOriginal",
        value: "2026:10:01 10:22:33 +02:00",
      },
      { name: "Exposure", id: "EXIF ExposureTime, FNumber", value: "1/120 s, f/1.8, ISO 100" },
    ],
    location: withLocation
      ? {
          source: "EXIF GPS",
          latitude: 46.0512333,
          longitude: 14.5056778,
          recorded: "46° 3' 4.44\" N, 14° 30' 20.44\" E",
          map_url: "https://www.google.com/maps/search/?api=1&query=46.0512333%2C14.5056778",
          altitude_m: 295.3,
          time_utc: "2026-10-01T08:22:33Z",
        }
      : null,
    groups: [
      {
        id: "file",
        title: "File",
        entries: [
          { name: "Format", value: "JPEG (image/jpeg)" },
          { name: "File size", value: "3,412,880 bytes" },
          { name: "Stored size", value: "4032 x 3024 px (before EXIF orientation)" },
        ],
      },
      {
        id: "exif-ifd0",
        title: "EXIF: image (IFD0)",
        entries: [
          { name: "Make", id: "0x010F", value: "Synthetic Camera Co" },
          { name: "Model", id: "0x0110", value: "Model 7" },
          { name: "Orientation", id: "0x0112", value: "6 (rotate 90 CW)" },
        ],
      },
      ...(gps.length ? [{ id: "exif-gps", title: "EXIF: GPS", entries: gps }] : []),
      {
        id: "xmp",
        title: "XMP",
        entries: [
          { name: "xmp:CreatorTool", value: "Synthetic Editor 3" },
          { name: "xmpMM:History[1]/stEvt:action", value: "saved" },
        ],
      },
    ],
    embedded: [
      {
        kind: "EXIF thumbnail",
        format: "JPEG",
        size_px: [160, 120],
        bytes: 5120,
        sha256: "sha256:" + "ab".repeat(32),
      },
    ],
    warnings: [
      "The camera maker's MakerNote is vendor-specific and was not decoded; its size and SHA-256 are listed.",
    ],
    entries: 17,
    truncated: false,
  };
}
