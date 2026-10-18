// Typed wrappers for the Tauri commands. The WebView is untrusted: it never sends a file path,
// passphrase or store location. Paths are chosen in native dialogs by the Rust core, and the
// passphrase is entered in the separate prompt window (ADR-010).
import { invoke } from "@tauri-apps/api/core";

import { noteActivity } from "../lib/idle";

import type {
  AppInfo,
  CaseCreated,
  CaseInfo,
  CaseOverview,
  ErrorKind,
  Exported,
  IdentityCreated,
  Item,
  JobOptions,
  JobRecord,
  JobResult,
  LimitsStatus,
  MinutiaeView,
  HeadExported,
  LogExported,
  Note,
  PackageExported,
  Preview,
  PromptContext,
  RegionPreview,
  ReportExported,
  Reproduction,
  SessionInfo,
  SheetExported,
  StoreCheck,
  StoreView,
  VerifiedReport,
  Verification,
} from "./types";

/** A failed command, with the category the Rust core assigned (no paths, no internals). */
export class IpcError extends Error {
  readonly kind: ErrorKind;

  constructor(kind: ErrorKind, message: string) {
    super(message);
    this.name = "IpcError";
    this.kind = kind;
  }
}

const KINDS: readonly string[] = ["invalid", "refused", "cancelled", "busy", "no_store", "unavailable"];

function isKind(value: unknown): value is ErrorKind {
  return typeof value === "string" && KINDS.includes(value);
}

function toIpcError(raw: unknown): IpcError {
  if (typeof raw === "object" && raw !== null && "kind" in raw && "message" in raw) {
    const { kind, message } = raw;
    if (isKind(kind) && typeof message === "string") {
      return new IpcError(kind, message);
    }
  }
  return new IpcError("unavailable", "the application core did not answer as expected");
}

async function call<T>(command: string, request?: Record<string, unknown>): Promise<T> {
  try {
    const result = await invoke<T>(command, request === undefined ? {} : { request });
    noteActivity(); // the engine answered: its idle clock restarted
    return result;
  } catch (raw) {
    const error = toIpcError(raw);
    if (error.kind === "refused") {
      noteActivity(); // a refusal is an answer from the engine too
    }
    throw error;
  }
}

/** True when a case command failed because the case is no longer unlocked (idle lock, engine restart). */
export function isLocked(error: unknown): boolean {
  return (
    error instanceof IpcError &&
    (error.kind === "unavailable" ||
      (error.kind === "refused" && error.message.includes("no case is unlocked")))
  );
}

export const ipc = {
  appInfo: () => call<AppInfo>("app_info"),
  chooseStore: () => call<StoreView>("choose_store"),
  refreshStore: () => call<StoreView>("refresh_store"),
  createIdentity: () => call<IdentityCreated>("create_identity"),
  createCase: (reference: string, legalBasis: string, retentionUntil: string) =>
    call<CaseCreated>("create_case", {
      reference,
      legal_basis: legalBasis,
      retention_until: retentionUntil,
    }),
  unlockCase: (caseId: string) => call<SessionInfo>("unlock_case", { case_id: caseId }),
  lockCase: () => call<{ locked: true }>("lock_case"),
  verifyStore: () => call<StoreCheck[]>("verify_store"),
  storeOverview: () => call<CaseOverview[]>("store_overview"),
  sessionStatus: () => call<{ unlocked: boolean; idle_timeout_s: number }>("session_status"),
  caseInfo: () => call<CaseInfo>("case_info"),
  setLegalHold: (on: boolean, reason: string) => call<CaseInfo>("set_legal_hold", { on, reason }),
  listItems: () => call<Item[]>("list_items"),
  addNote: (text: string, jobId: string | null, corrects: number | null) =>
    call<Note>("add_note", { text, job_id: jobId, sha256: null, corrects }),
  listNotes: (jobId: string | null) => call<Note[]>("list_notes", { job_id: jobId }),
  exportPackage: () => call<PackageExported>("export_package"),
  importEvidence: (source: string | null) => call<Item>("import_evidence", { source }),
  importReference: (source: string) => call<Item>("import_reference", { source }),
  verifyCase: () => call<Verification>("verify_case"),
  exportItem: (sha256: string, suggestedName: string | null) =>
    call<Exported>("export_item", { sha256, suggested_name: suggestedName }),
  preview: (sha256: string, maxSide: number) => call<Preview>("preview", { sha256, max_side: maxSide }),
  previewRegion: (sha256: string, x: number, y: number, width: number, height: number) =>
    call<RegionPreview>("preview_region", { sha256, x, y, width, height }),
  runJob: (options: JobOptions) => call<JobResult>("run_job", { ...options }),
  listJobs: () => call<JobRecord[]>("list_jobs"),
  getReport: (jobId: string) => call<VerifiedReport>("get_report", { job_id: jobId }),
  exportReport: (jobId: string) => call<ReportExported>("export_report", { job_id: jobId }),
  reproduceJob: (jobId: string) => call<Reproduction>("reproduce_job", { job_id: jobId }),
  exportLog: () => call<LogExported>("export_log"),
  exportHead: () => call<HeadExported>("export_head"),
  minutiae: (sha256: string) => call<MinutiaeView>("get_minutiae", { sha256 }),
  limitsOfUse: () => call<LimitsStatus>("limits_of_use"),
  exportComparison: (exportSha: string, referenceSha: string, referencePpi: number | null) =>
    call<SheetExported>("export_comparison", {
      export: exportSha,
      reference: referenceSha,
      reference_ppi: referencePpi,
    }),
};

/** Commands of the passphrase window only (capability `passphrase`). */
export const promptIpc = {
  context: () => call<PromptContext>("passphrase_context"),
  submit: (passphrase: string, confirmation: string | null) =>
    call<null>("passphrase_submit", { passphrase, confirmation }),
  cancel: () => call<null>("passphrase_cancel"),
};
