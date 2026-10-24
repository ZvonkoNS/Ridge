// The metadata an imported photo records about itself (FR-36): the position with a Google Maps link
// to copy, a short summary, and every group as a table. Everything shown was read and made
// display-safe by the trusted core; this view only lays it out. Ridge never opens the link: the
// workstation is offline and opening it would send the position to Google, so it is copied.
import { motion } from "motion/react";
import { useId, useState } from "react";

import type {
  MetadataEntry,
  MetadataGroup,
  PhotoLocation,
  PhotoMetadata,
  ProvenanceHints,
} from "../ipc/types";
import { usePhotoMetadata } from "../lib/usePhotoMetadata";
import { CopyButton } from "./CopyButton";

function matches(entry: MetadataEntry, find: string): boolean {
  const needle = find.toLowerCase();
  return [entry.name, entry.id ?? "", entry.value].some((v) => v.toLowerCase().includes(needle));
}

function Location({ location }: { location: PhotoLocation | null }) {
  if (!location) {
    return <p className="meta-none">No position is recorded in this photo&apos;s metadata.</p>;
  }
  const coordinates = `${location.latitude.toFixed(7)}, ${location.longitude.toFixed(7)}`;
  return (
    <div className="meta-location">
      <dl className="meta-facts">
        <dt>Position</dt>
        <dd>
          <span className="mono">{coordinates}</span> <CopyButton value={coordinates} what="coordinates" />
        </dd>
        <dt>As recorded</dt>
        <dd>
          {location.recorded} <span className="muted">({location.source})</span>
        </dd>
        {location.altitude_m !== undefined ? (
          <>
            <dt>Altitude</dt>
            <dd>{location.altitude_m} m</dd>
          </>
        ) : null}
        {location.time_utc ? (
          <>
            <dt>GPS time (UTC)</dt>
            <dd>{location.time_utc}</dd>
          </>
        ) : null}
        {location.horizontal_error_m !== undefined ? (
          <>
            <dt>Horizontal error</dt>
            <dd>{location.horizontal_error_m} m (as recorded)</dd>
          </>
        ) : null}
        <dt>Google Maps</dt>
        <dd>
          <code className="meta-link">{location.map_url}</code>{" "}
          <CopyButton value={location.map_url} what="Google Maps link" />
        </dd>
      </dl>
      <p className="meta-hint">
        Ridge does not open links. Paste the link into a browser on a computer with internet access; opening
        it sends this position to Google.
      </p>
    </div>
  );
}

function EntryTable({
  entries,
  caption,
  idHeading = "Tag",
}: {
  entries: MetadataEntry[];
  caption: string;
  idHeading?: string;
}) {
  const withIds = entries.some((e) => e.id);
  return (
    <table className="meta-table">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Name</th>
          {withIds ? <th scope="col">{idHeading}</th> : null}
          <th scope="col">Value</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e, i) => (
          <tr key={`${e.name}-${String(i)}`}>
            <td>{e.name}</td>
            {withIds ? <td className="mono">{e.id ?? ""}</td> : null}
            <td className="meta-value">{e.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Groups({ groups, find }: { groups: MetadataGroup[]; find: string }) {
  const shown = groups
    .map((g) => ({ ...g, entries: find ? g.entries.filter((e) => matches(e, find)) : g.entries }))
    .filter((g) => g.entries.length > 0);
  if (shown.length === 0) {
    return <p className="meta-none">No entry contains &quot;{find}&quot;.</p>;
  }
  return (
    <>
      {shown.map((g) => (
        <details
          key={`${g.id}-${find ? "found" : "all"}`}
          className="meta-group"
          open={find ? true : undefined}
        >
          <summary>
            {g.title} <span className="muted">({g.entries.length})</span>
          </summary>
          <EntryTable entries={g.entries} caption={g.title} />
        </details>
      ))}
    </>
  );
}

interface PanelProps {
  metadata: PhotoMetadata | null | undefined;
  loading?: boolean;
  failed?: boolean;
  /** Where the metadata comes from, for the heading ("photo" or "signed report"). */
  from?: "photo" | "report";
  /** Provenance hints (FR-42); absent for engines and reports before them. */
  provenance?: ProvenanceHints | null | undefined;
}

/** Signs that the photo may be a copy or an edit, as the trusted core states them; never verified. */
export function ProvenanceHintsList({ hints }: { hints: ProvenanceHints | null | undefined }) {
  if (!hints) {
    return null;
  }
  return (
    <section className="meta-provenance" aria-label="Provenance hints">
      <h4>Provenance hints</h4>
      <p className="meta-notice">{hints.notice}</p>
      {hints.hints.length > 0 ? (
        <ul className="meta-list">
          {hints.hints.map((h) => (
            <li key={h.id}>{h.text}</li>
          ))}
        </ul>
      ) : (
        <p className="meta-none">
          No hint: nothing in the file suggests a copy or an edit (which proves nothing).
        </p>
      )}
    </section>
  );
}

export function PhotoMetadataPanel({
  metadata,
  loading = false,
  failed = false,
  from = "photo",
  provenance,
}: PanelProps) {
  const headingId = useId();
  const [find, setFind] = useState("");
  const heading = from === "report" ? "Photo metadata (as recorded in this report)" : "Photo metadata";
  let body;
  if (loading) {
    body = <p className="meta-none">Reading the photo&apos;s metadata...</p>;
  } else if (failed) {
    body = <p className="meta-none">The metadata could not be read.</p>;
  } else if (!metadata) {
    body = (
      <p className="meta-none">Not recorded in this report (made before Ridge recorded photo metadata).</p>
    );
  } else {
    body = (
      <>
        <p className="meta-notice">{metadata.notice}</p>
        <h4>Location</h4>
        <Location location={metadata.location} />
        {metadata.summary.length > 0 ? (
          <>
            <h4>Summary</h4>
            <EntryTable entries={metadata.summary} caption="Summary" idHeading="From" />
          </>
        ) : null}
        <div className="meta-find">
          <label className="field">
            <span>Find in metadata</span>
            <input
              type="search"
              value={find}
              maxLength={100}
              onChange={(e) => {
                setFind(e.target.value);
              }}
            />
          </label>
          <span className="muted">
            {metadata.entries} entries{metadata.truncated ? ", some left out (see the notes below)" : ""}
          </span>
        </div>
        <Groups groups={metadata.groups} find={find.trim()} />
        {metadata.embedded.length > 0 ? (
          <>
            <h4>Embedded images</h4>
            <p className="muted">Recorded by size and SHA-256 only; Ridge does not show them.</p>
            <ul className="meta-list">
              {metadata.embedded.map((e, i) => (
                <li key={`${e.kind}-${String(i)}`}>
                  {e.kind}
                  {e.size_px
                    ? `, ${e.format ?? "image"} ${String(e.size_px[0])} × ${String(e.size_px[1])} px`
                    : ""}
                  {e.bytes !== undefined ? `, ${e.bytes.toLocaleString("en")} bytes` : ""}
                  {e.sha256 ? <span className="mono">, {e.sha256}</span> : null}
                  {e.note ? `, ${e.note}` : ""}
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {metadata.warnings.length > 0 ? (
          <>
            <h4>Notes on reading</h4>
            <ul className="meta-list">
              {metadata.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </>
        ) : null}
        <ProvenanceHintsList hints={provenance} />
      </>
    );
  }
  return (
    <motion.section
      className="meta-panel"
      aria-labelledby={headingId}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <h3 id={headingId}>{heading}</h3>
      {body}
    </motion.section>
  );
}

/** The panel for a stored photo, loaded from the sidecar (a logged read). */
export function StoredPhotoMetadata({
  sha256,
  onFailure,
}: {
  sha256: string;
  onFailure: (error: unknown) => void;
}) {
  const loaded = usePhotoMetadata(sha256, onFailure);
  return (
    <PhotoMetadataPanel
      metadata={loaded.metadata}
      provenance={loaded.provenance}
      loading={loaded.loading}
      failed={loaded.failed}
    />
  );
}
