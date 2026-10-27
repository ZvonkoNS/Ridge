// Result types of the Tauri commands (gui/src-tauri/src/commands), which forward the sidecar's
// JSON-RPC results (architecture §7.3). Hand-written and checked by the IPC tests (ADR-011).

export type ErrorKind = "invalid" | "refused" | "cancelled" | "busy" | "no_store" | "unavailable";

export interface AppInfo {
  gui: string;
  engine: { ridge: string; protocol: string; commit?: string; commit_source?: string };
}

export type CaseState = "active" | "locked" | "erasing" | "disposed" | "invalid";

export interface CaseSummary {
  case_id: string;
  state: CaseState;
  created_utc: string | null;
  disposed_utc: string | null;
}

export type IdentityStatus = { exists: false } | { exists: true; key_id: string; public_key: string };

export interface StoreView {
  path: string;
  identity: IdentityStatus;
  cases: CaseSummary[];
}

export interface IdentityCreated {
  key_id: string;
  public_key: string;
}

export interface SessionInfo {
  case_id: string;
  reference: string;
  retention_until: string;
  legal_hold: boolean;
}

export interface CaseInfo extends SessionInfo {
  legal_basis: string;
}

export interface CaseCreated {
  case_id: string;
  session: SessionInfo | null;
}

export type Role = "evidence" | "reference" | "print" | "debug" | "export" | "export-gray" | "minutiae";

export interface Item {
  sha256: string;
  role: Role;
  size: number;
  label: string;
  job_id: string | null;
  source: string | null;
}

export interface Preview {
  sha256: string;
  width: number;
  height: number;
  source_width: number;
  source_height: number;
  /** Resolution the file declares, when it is a plausible fingerprint resolution (250-2000 ppi). */
  ppi?: number | null;
  png_base64: string;
}

export interface RegionPreview extends Preview {
  x: number;
  y: number;
}

/**
 * Where the print came from, in the photo's pixels after EXIF orientation (the space of roi and
 * ruler): the frame the print image shows, and the outer edge of each kept area (pixel centres,
 * largest area first).
 */
export interface PrintArea {
  box_px: [number, number, number, number];
  outline_px: [number, number][][];
  parts: number;
  /** When the job rotated the finger upright (ADR-014): the tilted frame's corners and the rotation applied. */
  frame_px?: [number, number][];
  rotation_deg?: number | null;
}

/**
 * One metadata entry as the file records it, made display-safe by the trusted core (hidden and
 * control characters are written as <U+XXXX>). `id` is the tag (EXIF "0x010F", IPTC "2:80") or,
 * in the summary, the tags the line comes from.
 */
export interface MetadataEntry {
  name: string;
  id?: string;
  value: string;
}

export interface MetadataGroup {
  id: string;
  title: string;
  entries: MetadataEntry[];
}

/** The position the photo's metadata records (WGS 84 decimal degrees, rounded to 7 places). */
export interface PhotoLocation {
  source: string;
  latitude: number;
  longitude: number;
  recorded: string;
  /** A Google Maps link to copy; Ridge never opens it. */
  map_url: string;
  altitude_m?: number;
  time_utc?: string;
  datum?: string;
  horizontal_error_m?: number;
}

/** An image inside the file (such as the EXIF thumbnail), recorded by size and hash only. */
export interface EmbeddedImage {
  kind: string;
  format?: string;
  bytes?: number;
  sha256?: string;
  size_px?: [number, number];
  note?: string;
}

/** Everything Ridge read from an imported photo's metadata (schema ridge.photo-metadata/1, FR-36). */
export interface PhotoMetadata {
  schema: string;
  notice: string;
  summary: MetadataEntry[];
  location: PhotoLocation | null;
  groups: MetadataGroup[];
  embedded: EmbeddedImage[];
  warnings: string[];
  entries: number;
  truncated: boolean;
}

/** One provenance hint (FR-42): a sign the photo may be a copy or an edit, never a verified fact. */
export interface ProvenanceHint {
  id: string;
  text: string;
}

export interface ProvenanceHints {
  schema: string;
  hints: ProvenanceHint[];
  jpeg_quality_estimate: number | null;
  notice: string;
}

export interface PhotoMetadataView {
  sha256: string;
  role: "evidence" | "reference";
  metadata: PhotoMetadata;
  /** Absent from engines before FR-42. */
  provenance?: ProvenanceHints | null;
}

export interface Measurements {
  ridge_period_px: number;
  found_finger: boolean;
  output_scale: number;
  /** Absent in reports made before Ridge recorded it. */
  print_area?: PrintArea | null;
  /** The colour plane used (ADR-014); absent in reports made before it. */
  channel_used?: string;
  /** Share of the finger area removed as highlights when the specular mask was on; null when off. */
  specular_fraction?: number | null;
  /** Rotation applied to put the finger upright when that variant was on; null when off or not located. */
  upright_rotation_deg?: number | null;
  /** Ridge spacing used inside the print (photo pixels) when the local-frequency variant was on; null when off. */
  local_period_px?: { min: number; median: number; max: number } | null;
  /** The pad's median half-width and the unrolled angle when the rectify variant unrolled it; null when off. */
  rectification?: { half_width_px: number; max_angle_deg: number } | null;
}

export type ScaleMethod = "ruler" | "card" | "ridge-period" | "manual";

/** What the two scale points lie on (FR-31 a): a ruler, or an edge of an ISO/IEC 7810 ID-1 card. */
export type ReferenceKind = "ruler" | "id1-long" | "id1-short";

export interface ScaleInfo {
  method: ScaleMethod;
  px_per_mm: number;
  uncertainty_pct: number;
  assumed_ridge_period_mm?: number;
  /** The reference object the points lay on (ruler and card scales; absent in older reports). */
  reference?: string;
  /** Present when no scale reference was given: what the investigator can do about it. */
  notice?: string;
}

export type ExportInfo =
  | {
      produced: true;
      sha256: string;
      ppi: number;
      factor: number;
      transforms: string[];
      scale: ScaleInfo;
      /** The grayscale twin of the export (FR-37); absent in reports made before it. */
      grayscale?: { sha256: string; transforms: string[] };
      /** Present when the export was enlarged to reach its resolution (FR-32): no detail was gained. */
      resolution_note?: string;
    }
  | { produced: false; reason: string };

/** `image` names the stored role the tool scored (FR-37); absent in reports made before it. */
export type Nfiq2 =
  | { computed: true; score: number; version: string; label: string; image?: string }
  | { computed: false; reason: string; image?: string };

export interface Quality {
  nfiq2: Nfiq2;
}

export type MinutiaeSummary =
  | { produced: true; sha256: string; count: number; endings: number; bifurcations: number; label: string }
  | { produced: false; reason: string; label: string };

/** The limits-of-use section of a job report (PRD §12 item 8); absent in reports made before it. */
/** The Forensic Quality Manager key that signed the limits file (to be matched against the lab's register). */
export interface LimitsSigner {
  key_id: string;
  public_key: string;
}

export type LimitsSection =
  | { configured: false }
  | {
      configured: true;
      source: string;
      sha256: string;
      limits: Record<string, number | boolean | string[]>;
      within: boolean;
      warnings: string[];
      /** Absent in reports made before limits could be signed. */
      signed_by?: LimitsSigner | null;
    };

/** The store's limits of use, as `store.limits` returns them. */
/** A device-secret recovery file as the engine describes it (never the secret, ADR-012). */
export interface RecoveryFileInfo {
  key_id: string;
  fingerprint: string;
  created_utc: string;
  file: string;
}

/** One line of the read-only workstation check. */
export interface WorkstationFinding {
  topic: string;
  level: "ok" | "note" | "problem";
  text: string;
}

export type LimitsStatus =
  | { configured: false }
  | {
      configured: true;
      source: string;
      sha256: string;
      limits: Record<string, number | boolean | string[]>;
      signed_by: LimitsSigner | null;
    };

export interface JobResult {
  job_id: string;
  outputs: Item[];
  measurements: Measurements | null;
  export: ExportInfo | null;
  quality: Quality | null;
  minutiae: MinutiaeSummary | null;
  limits_of_use: LimitsSection | null;
  /** Absent in reports made before FR-38. */
  submission?: SubmissionRecord | null;
}

export interface MinutiaPoint {
  x: number;
  y: number;
  type: "ending" | "bifurcation";
  angle_deg: number;
  quality: number;
}

export interface MinutiaeSpace {
  width: number;
  height: number;
  ridge_period_px: number;
  minutiae: MinutiaPoint[];
}

export interface MinutiaeView {
  sha256: string;
  job_id: string | null;
  label: string;
  print: MinutiaeSpace | null;
  export: MinutiaeSpace | null;
}

/** Colour plane the ridge signal is taken from (ADR-014); "auto" picks the strongest. */
export type Channel = "green" | "red" | "blue" | "luma" | "auto";

/** Opt-in method variants (ADR-014): off by default, unvalidated, recorded in every report. */
export interface MethodOptions {
  channel: Channel;
  specular_mask: boolean;
  upright: boolean;
  local_frequency: boolean;
  rectify: boolean;
}

/** Options sent with `run_job`; every field is explicit, nothing is defaulted on the way. */
export interface JobOptions {
  evidence: string;
  period: number | null;
  min_quality: number;
  flip: boolean;
  crop: boolean;
  debug: boolean;
  export: boolean;
  mirror: boolean;
  ppi: number;
  ruler: [number, number, number, number, number] | null;
  reference: ReferenceKind;
  minutiae: boolean;
  roi: [number, number, number, number] | null;
  /** ANSI/NIST-ITL finger code stated by the examiner, 0 = unknown (FR-38). */
  finger_position: number;
  source_agency: string | null;
  options: MethodOptions;
}

/** The submission record of a job (FR-38): the examiner's statements and the unverified camera. */
export interface SubmissionRecord {
  finger_position: number;
  finger: string;
  source_agency: string | null;
  impression: string;
  capture_device: string | null;
  capture_device_note: string;
  notice: string;
}

export interface JobRecord {
  job_id: string;
  evidence_sha256: string;
  started_utc: string;
  ended_utc: string | null;
  result: "ok" | "failed" | "open";
  error: string | null;
  report_sha256: string | null;
  key_id: string | null;
}

export interface JobReport {
  schema: string;
  job_id: string;
  case_id: string;
  case_reference: string;
  created_utc: string;
  ridge: {
    version: string;
    /** Source commit (FR-34); absent in reports made before it was recorded. */
    commit?: string;
    commit_source?: string;
    python: string;
    platform: string;
    machine: string;
    dependencies: Record<string, string>;
  };
  input: {
    sha256: string;
    label: string;
    format?: string;
    size_px?: [number, number];
    source?: string | null;
    /** Absent in reports made before Ridge recorded the photo's metadata. */
    metadata?: PhotoMetadata | null;
    /** Absent in reports made before FR-42. */
    provenance?: ProvenanceHints | null;
  };
  parameters: Record<string, unknown>;
  measurements: Measurements | null;
  export: ExportInfo | null;
  quality: Quality | null;
  minutiae?: MinutiaeSummary | null;
  limits_of_use?: LimitsSection | null;
  submission?: SubmissionRecord | null;
  outputs: { role: Role; label: string; sha256: string; size: number }[];
  custody_head: string;
  signer: { key_id: string; public_key: string };
  disclaimer: string;
}

export interface VerifiedReport {
  job_id: string;
  key_id: string;
  verified: true;
  report: JobReport;
}

export interface Reproduction {
  identical: boolean;
  original_job: string;
  new_job: string;
  matched: string[];
  differing: string[];
  missing: string[];
  extra: string[];
  /** key -> [original, now] */
  environment_changes: Record<string, [unknown, unknown]>;
}

export interface Verification {
  ok: boolean;
  problems: string[];
  items: number;
  reports: number;
}

export interface Exported {
  exported: string;
  /** The conversion applied on export (tiff, bmp), or null/absent for the stored bytes (FR-32). */
  format?: string | null;
  /** SHA-256 of the bytes written (the stored item's hash when no conversion applied). */
  sha256?: string;
}

/** File formats a bulk export can convert image outputs to; "png" exports them as stored. */
export type ExportFormat = "png" | "tiff" | "bmp";

/** A scale sweep written to a new folder (FR-39): rescaled copies of one export over its uncertainty. */
export interface SweepExported extends Exported {
  files: number;
  factors: number[];
  index: string;
  uncertainty_pct: number | null;
}

/** A scale sweep written to a new folder (FR-39): rescaled copies of one export over its uncertainty. */
export interface SweepExported extends Exported {
  files: number;
  factors: number[];
  index: string;
  uncertainty_pct: number | null;
}

export interface ReportExported extends Exported {
  signature: string;
  key_id: string;
}

export interface HeadExported extends Exported {
  seq: number;
  head: string;
  key_id: string;
}

export interface LogExported extends Exported {
  entries: number;
  key_id: string;
}

export interface SheetExported extends Exported {
  sha256: string;
  ppi: number;
  reference_ppi: number;
  reference_ppi_source: string;
}

/** One case of a store-wide verification (`store.verify`). */
export interface StoreCheck {
  case_id: string;
  state: CaseState;
  checked: boolean;
  ok: boolean;
  reference: string | null;
  items: number;
  reports: number;
  problems: string[];
}

/** One custody log entry as the sidecar returns it (fields beyond these depend on the action). */
export interface CustodyEntry {
  seq: number;
  ts_utc: string;
  actor: string;
  action: string;
  result: string;
  [field: string]: unknown;
}

export interface CustodyPage {
  total: number;
  entries: CustodyEntry[];
}

/** A one-screen summary of the open case (read from the verified custody log). */
export interface CaseStatus {
  case_id: string;
  reference: string;
  retention_until: string;
  legal_hold: boolean;
  retention_reached: boolean;
  items: Record<string, number>;
  jobs: Record<string, number>;
  signed_reports: number;
  notes: number;
  entries: number;
  last_verified: string | null;
  last_verify_result: string | null;
  last_head_export: string | null;
}

/** The outcome of checking an exported file or package (every line is safe to show). */
export interface FileCheck {
  kind: "report" | "record" | "head" | "package" | "card" | "register" | "limits" | "backup";
  title: string;
  details: string[];
  key_id: string | null;
  holder: string | null;
}

/** The outcome of importing one or more evidence photos: each import is logged on its own. */
export interface ImportBatch {
  imported: Item[];
  refused: { name: string; message: string }[];
}

/** A disclosure package written to a new folder. */
export interface PackageExported {
  exported: string;
  package_id: string;
  reports: number;
  key_id: string;
}

/** An examiner note from the custody log (custody action `examiner.note`). */
export interface Note {
  seq: number;
  ts_utc: string;
  actor: string;
  text: string;
  job_id: string | null;
  sha256: string | null;
  /** Sequence number of the note this one corrects. */
  corrects: number | null;
}

/** One case of the store overview (read with the passphrase; nothing is written). */
export interface CaseOverview {
  case_id: string;
  state: CaseState;
  reference: string | null;
  retention_until: string | null;
  legal_hold: boolean | null;
  /** Retention date reached and no legal hold. */
  due: boolean | null;
  evidence: number | null;
  jobs: number | null;
  problem: string | null;
}

export interface PromptContext {
  purpose:
    | "create_identity"
    | "create_case"
    | "unlock"
    | "verify_store"
    | "store_overview"
    | "key_card"
    | "recovery_new"
    | "recovery_export"
    | "recovery_open"
    | "recovery_import";
  title: string;
  detail: string;
  confirm: boolean;
  min_chars: number;
  attempts_left: number;
}

/** One finding of the capture check (FR-54): fine, a reason to photograph again, or a note. */
export interface CaptureFinding {
  id: string;
  level: "ok" | "retake" | "note";
  text: string;
}

/** The capture check of a photo: indicative only, never a quality score of a print. */
export interface CaptureCheck {
  schema: string;
  sha256: string;
  width: number;
  height: number;
  finger_located: boolean;
  /** Share of the frame covered by the located finger (the whole frame when not located). */
  finger_share: number;
  ridge_spacing_px: number | null;
  clarity: number | null;
  glare_share: number | null;
  verdict: "retake" | "ok";
  findings: CaptureFinding[];
  notice: string;
  /** Present when a stored photo was checked. */
  role?: Role;
  label?: string;
}

/** The group of a triaged file, by what the capture check measured (FR-57). */
export type TriageGroup = "finger-ridges" | "ridges-no-finger" | "finger-unclear" | "nothing" | "refused";

/** One file of a triaged folder: its capture check and group, or why it was not read. */
export interface TriageRow {
  order: number;
  /** Relative to the folder, with "/" separators. */
  file: string;
  bytes: number;
  group: TriageGroup;
  check: Omit<CaptureCheck, "notice"> | null;
  reason: string;
}

/** A folder's photos in reading order (FR-57): a reading order for the examiner, never a quality judgement. */
export interface Triage {
  schema: string;
  ridge_version: string;
  folder: string;
  recursive: boolean;
  photos: number;
  other_files: number;
  counts: Record<TriageGroup, number>;
  groups: Record<TriageGroup, string>;
  thresholds: Record<string, number>;
  rows: TriageRow[];
  notice: string;
  /** Present when the index was saved. */
  index?: { path: string; sha256: string };
}

/** One feature the examiner marked on an output image (FR-55): pixel position, kind, optional label. */
export interface AnnotationMark {
  n: number;
  x: number;
  y: number;
  kind: "ending" | "bifurcation" | "other";
  label: string | null;
}

/** An annotation set as recorded in the custody log and signed right after it. */
export interface Annotation {
  seq: number;
  ts_utc: string;
  actor: string;
  job_id: string;
  /** The output image the marks are on. */
  sha256: string;
  role: Role;
  image: { width: number; height: number };
  marks: AnnotationMark[];
  note: string | null;
  replaces: number | null;
  /** The chain.sign entry that followed the set; null until the list is reloaded after signing. */
  signed_seq: number | null;
}

/** A mark as the examiner sends it: the sidecar numbers the marks. */
export interface NewMark {
  x: number;
  y: number;
  kind: AnnotationMark["kind"];
  label: string | null;
}

export interface AnnotatedExport {
  exported: string;
  sha256: string;
  seq: number;
  marks: number;
}
