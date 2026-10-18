// NAFIS/AFIS candidate images shown beside a Ridge export for MANUAL comparison (FR-52). View
// only: nothing is aligned, matched or scored. The sheet export puts both at one scale with
// 10 mm bars; the reference's resolution comes from its file or the examiner, never a guess.
import { useState } from "react";

import { ExhibitLabel } from "../components/ExhibitLabel";
import { ImageViewer } from "../components/ImageViewer";
import type { ScaleSource } from "../components/ScaleBar";
import { Button, Hash, Notice } from "../components/ui";
import { ipc } from "../ipc/commands";
import type { Item } from "../ipc/types";
import { usePreview } from "../lib/usePreview";

interface Props {
  items: Item[];
  onFailure: (error: unknown) => void;
  onChanged: () => void;
  notify: (message: string) => void;
}

/** A scale from a resolution in pixels per inch (no uncertainty is known for a declared value). */
export function scaleFrom(ppi: number | null, method: "file" | "examiner"): ScaleSource | null {
  return ppi ? { pxPerMm: ppi / 25.4, method, uncertaintyPct: null } : null;
}

export function ReferencesSection({ items, onFailure, onChanged, notify }: Props) {
  const references = items.filter((i) => i.role === "reference");
  const exports = items.filter((i) => i.role === "export");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState<"import" | "sheet" | null>(null);
  const [exportSha, setExportSha] = useState<string>("");
  const [referenceSha, setReferenceSha] = useState<string>("");
  const [referencePpi, setReferencePpi] = useState("");
  const left = usePreview(exportSha || null, onFailure);
  const right = usePreview(referenceSha || null, onFailure);
  const exportItem = exports.find((i) => i.sha256 === exportSha);
  const referenceItem = references.find((i) => i.sha256 === referenceSha);
  const typedPpi = Number(referencePpi);
  const exportScale = scaleFrom(left.ppi, "file");
  const referenceScale =
    referencePpi.trim() !== "" && typedPpi >= 250 && typedPpi <= 2000
      ? scaleFrom(typedPpi, "examiner")
      : scaleFrom(right.ppi, "file");
  const [linked, setLinked] = useState(false);
  const [screenPxPerMm, setScreenPxPerMm] = useState(12);
  const canLink = exportScale !== null && referenceScale !== null && Boolean(exportItem && referenceItem);
  const link = linked && canLink;

  const importReference = async () => {
    setBusy("import");
    try {
      const item = await ipc.importReference(source);
      notify(`Reference ${item.label} imported and logged; it is never processed.`);
      setSource("");
      setReferenceSha(item.sha256);
      setReferencePpi(""); // a typed resolution belongs to the reference it was typed for
      onChanged();
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };

  const exportSheet = async () => {
    const ppi = referencePpi.trim() === "" ? null : Number(referencePpi);
    setBusy("sheet");
    try {
      const sheet = await ipc.exportComparison(exportSha, referenceSha, ppi);
      notify(
        `Comparison sheet exported at ${sheet.ppi} ppi (reference ${sheet.reference_ppi} ppi from the ${sheet.reference_ppi_source}).`,
      );
      onChanged();
    } catch (error) {
      onFailure(error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="section section-wide">
      <div className="refs-head">
        <form
          className="import import-inline"
          onSubmit={(e) => {
            e.preventDefault();
            void importReference();
          }}
        >
          <label className="field">
            <span>Where the reference comes from</span>
            <input
              value={source}
              required
              maxLength={200}
              placeholder="NAFIS candidate 1, request 2026/77"
              onChange={(e) => {
                setSource(e.target.value);
              }}
            />
          </label>
          <Button variant="primary" type="submit" busy={busy === "import"} disabled={source.trim() === ""}>
            Import reference...
          </Button>
        </form>
        <div className="refs-pick">
          <label className="field">
            <span>Ridge export</span>
            <select
              value={exportSha}
              onChange={(e) => {
                setExportSha(e.target.value);
              }}
            >
              <option value="">Choose an export</option>
              {exports.map((i) => (
                <option key={i.sha256} value={i.sha256}>
                  {i.label} · {i.sha256.slice(0, 10)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Reference</span>
            <select
              value={referenceSha}
              onChange={(e) => {
                setReferenceSha(e.target.value);
                setReferencePpi(""); // never carry one reference's resolution over to another
              }}
            >
              <option value="">Choose a reference</option>
              {references.map((i) => (
                <option key={i.sha256} value={i.sha256}>
                  {i.source ?? i.label} · {i.sha256.slice(0, 10)}
                </option>
              ))}
            </select>
          </label>
          <label className="field field-narrow">
            <span>Reference ppi</span>
            <input
              inputMode="decimal"
              placeholder="from file"
              value={referencePpi}
              onChange={(e) => {
                setReferencePpi(e.target.value);
              }}
            />
          </label>
          <Button
            onClick={() => void exportSheet()}
            busy={busy === "sheet"}
            disabled={!exportSha || !referenceSha}
          >
            Export comparison sheet...
          </Button>
        </div>
      </div>
      <Notice tone="caution">
        View only. Ridge does not align, match or score: the comparison is the examiner&apos;s.
      </Notice>
      <div className="toolbar">
        <label className="overlay-toggle overlay-toggle-start">
          <input
            type="checkbox"
            checked={link}
            disabled={!canLink}
            onChange={(e) => {
              setLinked(e.target.checked);
            }}
          />
          Equal scale: link the zoom of both images
        </label>
        {!canLink && exportItem && referenceItem ? (
          <span className="toolbar-note">
            Needs the reference&apos;s resolution, from its file or typed above (250-2000 ppi).
          </span>
        ) : null}
      </div>
      <div className="review-pair">
        <div className="review-side">
          {exportItem ? (
            <ImageViewer
              title="Ridge comparison export"
              url={left.url}
              bitmap={left.bitmap}
              source={left.source}
              zoom={link ? screenPxPerMm / exportScale.pxPerMm : undefined}
              onZoom={(z) => {
                if (exportScale) {
                  setScreenPxPerMm(z * exportScale.pxPerMm);
                }
              }}
              label={(zoom) => (
                <ExhibitLabel
                  role="export"
                  sha256={exportItem.sha256}
                  detail={`${exportItem.label}; scale method and uncertainty: see the job report`}
                  scale={exportScale}
                  zoom={zoom}
                />
              )}
            />
          ) : (
            <div className="viewer-placeholder">Choose a Ridge export</div>
          )}
        </div>
        <div className="review-side">
          {referenceItem ? (
            <ImageViewer
              title="Reference image"
              url={right.url}
              bitmap={right.bitmap}
              source={right.source}
              zoom={link ? screenPxPerMm / referenceScale.pxPerMm : undefined}
              onZoom={(z) => {
                if (referenceScale) {
                  setScreenPxPerMm(z * referenceScale.pxPerMm);
                }
              }}
              label={(zoom) => (
                <ExhibitLabel
                  role="reference"
                  sha256={referenceItem.sha256}
                  detail={referenceItem.source ?? referenceItem.label}
                  scale={referenceScale}
                  zoom={zoom}
                />
              )}
            />
          ) : (
            <div className="viewer-placeholder">Choose or import a reference</div>
          )}
        </div>
      </div>
      {references.length > 0 ? (
        <p className="review-foot">
          {references.length} reference{references.length === 1 ? "" : "s"} in this case:{" "}
          {references.map((r, i) => (
            <span key={r.sha256}>
              {i > 0 ? ", " : ""}
              {r.source ?? r.label} <Hash value={r.sha256} length={8} />
            </span>
          ))}
        </p>
      ) : null}
    </div>
  );
}
