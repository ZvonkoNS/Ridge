// The exhibit label on every image: what it is, its SHA-256, and for processed images the
// mandatory statement that it is not an identification (desktop_gui_tauri_standards.md §6).
import type { Role } from "../ipc/types";
import { ScaleBar, type ScaleSource } from "./ScaleBar";

export const PROCESSED_LABEL = "Processed image - not an identification";

const ROLE_NAMES: Record<Role, string> = {
  evidence: "Original photo",
  reference: "Reference image (view only)",
  print: "Extracted print",
  debug: "Debug image",
  export: "Comparison export",
  minutiae: "Minutiae",
};

export function roleName(role: Role): string {
  return ROLE_NAMES[role];
}

interface Props {
  role: Role;
  sha256: string;
  detail?: string | undefined;
  scale?: ScaleSource | null | undefined;
  zoom: number;
}

export function ExhibitLabel({ role, sha256, detail, scale, zoom }: Props) {
  const processed = role === "print" || role === "debug" || role === "export";
  return (
    <div className="exhibit">
      <div className="exhibit-row">
        <span className="exhibit-role">{roleName(role)}</span>
        {detail ? <span className="exhibit-detail">{detail}</span> : null}
        <span className="exhibit-hash" title={`SHA-256 ${sha256}`}>
          <abbr title="SHA-256">sha256</abbr> {sha256.slice(0, 12)}
        </span>
      </div>
      {processed ? <p className="exhibit-warning">{PROCESSED_LABEL}</p> : null}
      {scale ? <ScaleBar source={scale} zoom={zoom} /> : <p className="exhibit-noscale">Scale unknown</p>}
    </div>
  );
}
