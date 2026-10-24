// DEVELOPMENT PREVIEW ONLY: lets `npm run dev` render every screen in a plain browser, with a
// mocked IPC bridge and SYNTHETIC images drawn here (concentric sine ridges, no biometric data).
// main.tsx installs it only when import.meta.env.DEV is true and no Tauri core is present, so
// production builds drop this module entirely (checked by the GUI gate).
import type { Item, JobRecord, JobReport, JobResult, MinutiaeSpace, Note, Preview } from "../ipc/types";
import { previewMetadata } from "./previewMetadata";

const CASE_ID = "0f8fad5b-d9cb-469f-a165-70867728950e";
const KEY_ID = "5a1c09e3b47d2f68";
const hex = (seed: number): string =>
  Array.from({ length: 64 }, (_, i) => ((seed * 7 + i * 13) % 16).toString(16)).join("");

const evidence: Item[] = [
  {
    sha256: hex(1),
    role: "evidence",
    size: 3_412_880,
    label: "IMG_0042.jpg",
    job_id: null,
    source: "Exhibit 12, phone A",
  },
  {
    sha256: hex(2),
    role: "evidence",
    size: 2_904_112,
    label: "IMG_0043.jpg",
    job_id: null,
    source: "Exhibit 12, phone A",
  },
];
const items: Item[] = [...evidence];
const jobs: JobRecord[] = [];
const reports = new Map<string, JobReport>();
const notes: Note[] = [];

function draw(
  width: number,
  height: number,
  mode: "photo" | "print" | "export",
  maxSide: number,
): Preview & { png: string } {
  const scale = Math.min(1, maxSide / Math.max(width, height));
  const w = Math.round(width * scale);
  const h = Math.round(height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("no canvas");
  }
  const image = ctx.createImageData(w, h);
  const cx = w * 0.5;
  const cy = h * 0.55;
  const period = 18 * scale;
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const dx = (x - cx) / (w * 0.22);
      const dy = (y - cy) / (h * 0.36);
      const inside = dx * dx + dy * dy < 1;
      const r = Math.hypot(x - cx, (y - cy) * 0.8) + 6 * Math.sin(Math.atan2(y - cy, x - cx) * 2);
      const ridge = 0.5 + 0.5 * Math.cos((2 * Math.PI * r) / period);
      const i = (y * w + x) * 4;
      let v: [number, number, number];
      if (mode === "photo") {
        v = inside ? [196 - 40 * ridge, 150 - 34 * ridge, 128 - 30 * ridge] : [70, 74, 82];
      } else {
        const on = inside && ridge > 0.5 ? 255 : 0;
        const g = mode === "print" ? on : 255 - on;
        v = [g, g, g];
      }
      image.data[i] = v[0];
      image.data[i + 1] = v[1];
      image.data[i + 2] = v[2];
      image.data[i + 3] = 255;
    }
  }
  ctx.putImageData(image, 0, 0);
  const png = canvas.toDataURL("image/png").split(",")[1] ?? "";
  return {
    sha256: "",
    width: w,
    height: h,
    source_width: width,
    source_height: height,
    png_base64: png,
    png,
  };
}

const SIZES: Record<string, [number, number, "photo" | "print" | "export"]> = {};
for (const e of evidence) {
  SIZES[e.sha256] = [3024, 4032, "photo"];
}

/** The synthetic finger's print area in the 3024 x 4032 photo: an ellipse inside the finger. */
const PRINT_AREA = {
  box_px: [912, 960, 1201, 2516] as [number, number, number, number],
  outline_px: [
    Array.from({ length: 32 }, (_, i): [number, number] => {
      const a = (i / 32) * 2 * Math.PI;
      return [Math.round(1512 + 565 * Math.cos(a)), Math.round(2218 + 1225 * Math.sin(a))];
    }),
  ],
  parts: 1,
};

function runJob(request: Record<string, unknown>): JobResult {
  const n = jobs.length + 1;
  const jobId = `${String(n).padStart(8, "0")}-1111-4222-8333-444455556666`;
  const outputs: Item[] = [
    {
      sha256: hex(10 + n),
      role: "print",
      size: 812_441,
      label: "IMG_0042_fingerprint.png",
      job_id: jobId,
      source: null,
    },
    {
      sha256: hex(20 + n),
      role: "export",
      size: 402_118,
      label: "IMG_0042_comparison_500ppi.png",
      job_id: jobId,
      source: null,
    },
    {
      sha256: hex(70 + n),
      role: "export-gray",
      size: 611_204,
      label: "IMG_0042_comparison_gray_500ppi.png",
      job_id: jobId,
      source: null,
    },
  ];
  SIZES[hex(10 + n)] = [1180, 1500, "print"];
  SIZES[hex(20 + n)] = [760, 966, "export"];
  SIZES[hex(70 + n)] = [760, 966, "export"]; // drawn like the export: synthetic preview only
  if (request.minutiae === true) {
    outputs.push({
      sha256: hex(50 + n),
      role: "minutiae",
      size: 4_096,
      label: "IMG_0042_minutiae.json",
      job_id: jobId,
      source: null,
    });
  }
  items.push(...outputs);
  const ruler = request.ruler !== null;
  const result: JobResult = {
    job_id: jobId,
    outputs,
    measurements: { ridge_period_px: 17.92, found_finger: true, output_scale: 1, print_area: PRINT_AREA },
    export: {
      produced: true,
      sha256: hex(20 + n),
      ppi: 500,
      factor: 0.98,
      transforms: [
        "polarity:dark-ridges",
        "mirror:horizontal",
        `scale:500ppi:${ruler ? "ruler" : "ridge-period"}`,
      ],
      scale: ruler
        ? { method: "ruler", px_per_mm: 20.0, uncertainty_pct: 0.25 }
        : {
            method: "ridge-period",
            px_per_mm: 38.1,
            uncertainty_pct: 15,
            assumed_ridge_period_mm: 0.47,
            notice:
              "No scale reference was given: the export scale is estimated from the ridge spacing (synthetic preview).",
          },
      grayscale: {
        sha256: hex(70 + n),
        transforms: [
          "tone:grayscale",
          "polarity:dark-ridges",
          "mirror:horizontal",
          `scale:500ppi:${ruler ? "ruler" : "ridge-period"}`,
        ],
      },
    },
    quality: {
      nfiq2: {
        computed: false,
        reason: "NFIQ 2 is not configured on this workstation",
        image: "export-gray",
      },
    },
    minutiae:
      request.minutiae === true
        ? {
            produced: true,
            sha256: hex(50 + n),
            count: 24,
            endings: 15,
            bifurcations: 9,
            label: "unvalidated automatic minutiae for examiner review; not used for any matching",
          }
        : null,
    limits_of_use: ruler ? LIMITS_WITHIN : LIMITS_OUTSIDE,
  };
  jobs.push({
    job_id: jobId,
    evidence_sha256: String(request.evidence),
    started_utc: "2026-10-18T08:12:03Z",
    ended_utc: "2026-10-18T08:12:09Z",
    result: "ok",
    error: null,
    report_sha256: hex(30 + n),
    key_id: KEY_ID,
  });
  reports.set(jobId, {
    schema: "ridge.job-report/1",
    job_id: jobId,
    case_id: CASE_ID,
    case_reference: "KT-2026-0001",
    created_utc: "2026-10-18T08:12:09Z",
    ridge: { version: "0.2.0", python: "3.13.5", platform: "Windows-11", machine: "AMD64", dependencies: {} },
    input: {
      sha256: String(request.evidence),
      label: "IMG_0042.jpg",
      source: "Exhibit 12, phone A",
      metadata: previewMetadata(String(request.evidence) === hex(1)),
    },
    parameters: { ...request },
    measurements: result.measurements,
    export: result.export,
    quality: result.quality,
    outputs: outputs.map(({ role, label, sha256, size }) => ({ role, label, sha256, size })),
    custody_head: hex(40 + n),
    signer: { key_id: KEY_ID, public_key: "AAAA" },
    disclaimer: "Image enhancement only. Ridge does not identify anyone and draws no conclusions.",
  });
  return result;
}

const LIMITS = { min_ridge_period_px: 7, require_ruler: true, architectures: ["AMD64"] };
const LIMITS_WITHIN = {
  configured: true as const,
  source: "VR-2027-01 (synthetic preview)",
  sha256: hex(60),
  limits: LIMITS,
  within: true,
  warnings: [],
};
const LIMITS_OUTSIDE = {
  ...LIMITS_WITHIN,
  within: false,
  warnings: ["the export scale comes from ridge-period; the limits require a ruler in the photo"],
};

function marks(width: number, height: number, period: number): MinutiaeSpace {
  const minutiae = Array.from({ length: 24 }, (_, i) => {
    const t = (i / 24) * 2 * Math.PI;
    const r = 0.12 + (0.3 * ((i * 7) % 10)) / 10;
    return {
      x: Math.round(width * (0.5 + r * 0.45 * Math.cos(t))),
      y: Math.round(height * (0.55 + r * 0.6 * Math.sin(t))),
      type: i % 3 === 0 ? ("bifurcation" as const) : ("ending" as const),
      angle_deg: (i * 47) % 360,
      quality: 60,
    };
  });
  return { width, height, ridge_period_px: period, minutiae };
}

type Handler = (request: Record<string, unknown>) => unknown;

const store = {
  path: "D:\\Cases\\Ridge store",
  identity: { exists: true, key_id: KEY_ID, public_key: "AAAA" },
  cases: [
    { case_id: CASE_ID, state: "active", created_utc: "2026-10-16T09:30:00Z", disposed_utc: null },
    {
      case_id: "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1",
      state: "disposed",
      created_utc: "2026-09-01T10:00:00Z",
      disposed_utc: "2026-10-01T10:00:00Z",
    },
  ],
};
const session = {
  case_id: CASE_ID,
  reference: "KT-2026-0001",
  retention_until: "2031-12-31",
  legal_hold: false,
};

function previewCheck(sha256: string, role: string | null) {
  return {
    schema: "ridge.capture-check/1",
    sha256,
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
      { id: "spacing", level: "ok", text: "About 11.4 px per ridge." },
      { id: "clarity", level: "ok", text: "The ridge pattern is clear (peak share 0.05)." },
      {
        id: "glare",
        level: "retake",
        text: "Glare covers 8 % of the finger: move the light, switch off the flash or diffuse it.",
      },
      {
        id: "scale",
        level: "note",
        text: "Ridge cannot see whether a ruler or an ISO/IEC 7810 ID-1 card lies in the plane of the finger pad; with one, the scale is measured instead of estimated.",
      },
    ],
    notice:
      "This check only says whether photographing the finger again would help. It is not a quality score of a print and says nothing about identification.",
    ...(role === null ? {} : { role, label: "IMG_0412.jpg" }),
  };
}

const handlers: Record<string, Handler> = {
  check_photo: () => previewCheck(hex(5), null),
  check_evidence: (r) => previewCheck(String(r.sha256), "evidence"),
  app_info: () => ({ gui: "0.2.0", engine: { ridge: "0.2.0", protocol: "ridge.sidecar/1" } }),
  refresh_store: () => store,
  choose_store: () => store,
  unlock_case: () => session,
  lock_case: () => ({ locked: true }),
  session_status: () => ({ unlocked: true, idle_timeout_s: 900 }),
  export_package: () => ({
    exported: "D:/Exports/Ridge disclosure package",
    package_id: "6f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f",
    reports: reports.size,
    key_id: KEY_ID,
  }),
  case_info: () => ({ ...session, legal_basis: "ZKP art. 149 (synthetic preview)" }),
  case_status: () => ({
    case_id: session.case_id,
    reference: session.reference,
    retention_until: session.retention_until,
    legal_hold: session.legal_hold,
    retention_reached: false,
    items: items.reduce<Record<string, number>>((n, i) => ({ ...n, [i.role]: (n[i.role] ?? 0) + 1 }), {}),
    jobs: {
      ok: jobs.filter((j) => j.result === "ok").length,
      failed: jobs.filter((j) => j.result !== "ok").length,
    },
    signed_reports: jobs.filter((j) => j.report_sha256 !== null).length,
    notes: 1,
    entries: 12 + jobs.length * 6,
    last_verified: "2026-10-16T09:33:00Z",
    last_verify_result: "ok",
    last_head_export: null,
  }),
  set_legal_hold: (r) => ({ ...session, legal_basis: "ZKP art. 149 (synthetic preview)", legal_hold: r.on }),
  list_items: () => [...items],
  list_jobs: () => [...jobs],
  get_report: (r) => ({
    job_id: r.job_id,
    key_id: KEY_ID,
    verified: true,
    report: reports.get(String(r.job_id)),
  }),
  run_job: (r) => runJob(r),
  verify_case: () => ({ ok: true, problems: [], items: items.length, reports: reports.size }),
  preview: (r) => {
    const sha = String(r.sha256);
    const [w, h, mode] = SIZES[sha] ?? [800, 600, "photo"];
    const p = draw(w, h, mode, Math.min(Number(r.max_side), 900));
    return { ...p, sha256: sha };
  },
  export_item: () => ({ exported: "D:\\Exports\\IMG_0042_comparison_500ppi.png" }),
  photo_metadata: (r) => ({
    sha256: r.sha256,
    role: "evidence",
    metadata: previewMetadata(String(r.sha256) === hex(1)),
  }),
  get_minutiae: (r) => ({
    sha256: r.sha256,
    job_id: null,
    label: "unvalidated automatic minutiae for examiner review; not used for any matching",
    print: marks(1180, 1500, 17.9),
    export: marks(760, 966, 11.5),
  }),
  limits_of_use: () => ({
    configured: true,
    source: LIMITS_WITHIN.source,
    sha256: LIMITS_WITHIN.sha256,
    limits: LIMITS,
  }),
  workstation_check: () => [
    { topic: "Ridge", level: "ok", text: "Ridge 0.2.0, commit 9bc5ae0d1f2a (build)" },
    {
      topic: "Platform",
      level: "ok",
      text: "Windows-11, AMD64, Python 3.13.5. Results are reproducible per architecture (x86_64)",
    },
    {
      topic: "OS keystore",
      level: "ok",
      text: "the Ridge device secret is present (not shown). Store backups do not carry it (ADR-012)",
    },
    { topic: "Identity", level: "ok", text: `examiner signing key ${KEY_ID}` },
    { topic: "Store", level: "ok", text: "D:\\Cases\\Ridge store (2 active)" },
    { topic: "Limits of use", level: "note", text: "VR-2027-01, not signed" },
  ],
  export_log: () => ({ exported: "D:\\Exports\\record.json", entries: 42, key_id: KEY_ID }),
  store_overview: () => [
    {
      case_id: CASE_ID,
      state: "active",
      reference: "KT-2026-0001",
      retention_until: "2031-12-31",
      legal_hold: true,
      due: false,
      evidence: evidence.length,
      jobs: jobs.length,
      problem: null,
    },
    {
      case_id: store.cases[1]?.case_id,
      state: "disposed",
      reference: null,
      retention_until: null,
      legal_hold: null,
      due: null,
      evidence: null,
      jobs: null,
      problem: null,
    },
  ],
  list_notes: (r) =>
    notes.filter((n) => (!r.job_id || n.job_id === r.job_id) && (!r.sha256 || n.sha256 === r.sha256)),
  add_note: (r) => {
    const note: Note = {
      seq: 40 + notes.length,
      ts_utc: new Date().toISOString().slice(0, 19) + "Z",
      actor: "examiner (preview)",
      text: String(r.text),
      job_id: typeof r.job_id === "string" ? r.job_id : null,
      sha256: typeof r.sha256 === "string" ? r.sha256 : null,
      corrects: typeof r.corrects === "number" ? r.corrects : null,
    };
    notes.push(note);
    return note;
  },
  custody_log: (r) => {
    const kind = typeof r.action === "string" ? r.action : null;
    const all = previewLog().filter((e) => !kind || e.action === kind || e.action.startsWith(`${kind}.`));
    const offset = Number(r.offset ?? 0);
    return { total: all.length, entries: all.slice(offset, offset + Number(r.limit ?? 100)) };
  },
  check_exported: (r) => ({
    kind: r.folder ? "package" : "report",
    title: r.folder ? "Disclosure package" : "Signed job report",
    details: [
      "Synthetic preview: nothing was read from disk",
      r.with_register ? `Key ${KEY_ID} registered to Examiner (preview)` : `Signed with key ${KEY_ID}`,
    ],
    key_id: KEY_ID,
    holder: r.with_register ? "Examiner (preview)" : null,
  }),
  export_key_card: (r) => ({
    key_id: KEY_ID,
    holder: String(r.holder),
    exported: "D:\\Exports\\ridge_key_card.json",
  }),
  export_report_html: (r) => ({ exported: "D:\\Exports\\ridge_job_report.html", job_id: r.job_id }),
  export_cover: (r) => ({ exported: "D:\\Exports\\ridge_submission_cover.html", job_id: r.job_id }),
  export_sweep: () => ({
    exported: "D:\\Exports\\Ridge scale sweep",
    files: 3,
    factors: [0.85, 1, 1.15],
    index: "SWEEP.csv",
    uncertainty_pct: 15,
  }),
  import_evidence: () => ({
    imported: [],
    refused: [{ name: "IMG_0099.gif", message: "the preview imports nothing (synthetic data only)" }],
  }),
};

/** A synthetic custody log, newest first, built from what the preview session did. */
function previewLog(): { seq: number; ts_utc: string; actor: string; action: string; result: string }[] {
  const base = [
    { action: "case.create", label: undefined },
    ...evidence.map((e) => ({ action: "evidence.import", label: e.label })),
    { action: "case.verify", label: undefined },
  ];
  const rows = base.map((b, seq) => ({
    seq,
    ts_utc: `2026-10-16T09:${String(30 + seq).padStart(2, "0")}:00Z`,
    actor: "examiner (preview)",
    action: b.action,
    result: "ok",
    ...(b.label ? { label: b.label, source: "Exhibit 12, phone A" } : {}),
  }));
  const later = notes.map((n) => ({
    seq: n.seq,
    ts_utc: n.ts_utc,
    actor: n.actor,
    action: "examiner.note",
    result: "ok",
    text: n.text,
  }));
  return [...rows, ...later].reverse();
}

/** Install the mocked bridge (development preview only). */
export function installPreview(): void {
  const target = window as unknown as { __TAURI_INTERNALS__?: unknown };
  target.__TAURI_INTERNALS__ = {
    invoke: (command: string, args?: { request?: Record<string, unknown> }) =>
      new Promise((resolve, reject) => {
        const handler = handlers[command];
        window.setTimeout(
          () => {
            if (handler) {
              resolve(handler(args?.request ?? {}));
            } else {
              // shaped like a Rust core error so the UI shows it as a refusal
              // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
              reject({ kind: "refused", message: `the preview does not mock ${command}` });
            }
          },
          command === "run_job" ? 700 : 60,
        );
      }),
    transformCallback: () => 0,
  };
}
