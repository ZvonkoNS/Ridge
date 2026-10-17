# Handoff_12.md

Date/time (ISO 8601 with offset): 2026-10-17T11:05+02:00
Author/agent: Claude Code (claude-opus-5-5), end of the autonomous development window (about 08:35–12:35+02:00)
Project: Ridge
Branch: `m5-roi-source` (built on `m5-store-listing`) → PR after the stack below

## 1. Scope of this branch

| Part | What |
| --- | --- |
| Region of interest (**proposed FR-35**, PO confirmation pending) | `JobParams.roi` (x, y, width, height in the EXIF-oriented photo) is validated before a job starts: four whole numbers, start inside the photo, at least 32 × 32 px. A malformed ROI starts no job. The photo is cut to the ROI before extraction. An ROI outside the photo fails the job with a logged reason. The ROI is recorded in the report parameters, shown in `ridge-case report`, and rebuilt by `reproduce`; reports from before the ROI have none. Ruler points stay in full-photo coordinates, which is valid because the scale depends only on their distance. CLI `--roi X Y W H` (single evidence only); sidecar `job.run` `roi` |
| Evidence source note (FR-21 extension) | `ridge-case import --source "Exhibit 12, phone A"` and sidecar `case.import` `source`. The note is cleaned (control characters refused), kept encrypted in the custody log, listed by `ridge-case list`, and repeated as `input.source` in every job report on the photo |
| CLI split (PR #9 review, AGENTS.md file-size rule) | `ridge/case/cli.py` (497 lines) is split by responsibility. `cli.py` (320 lines) keeps the entry point and the store, case and extract commands. `cli_records.py` holds jobs, report, reproduce, check-report, log and check-log. `cli_compare.py` holds import-reference and compare. `cli_common.py` holds the keystore factory, KDF cost, passphrase prompt and output; tests patch `cli_common`. Behaviour is unchanged |


The previous branch (`m5-store-listing`, PR #10, Handoff_11) added `ridge-case cases` / `store.cases` (store listing without a passphrase) and `extract --keep-going`.

## 2. Evidence

`tests/test_case_roi.py` covers:

- a whole-photo ROI produces outputs identical to no ROI;
- a partial ROI changes the print and reproduces bit for bit;
- malformed ROIs (negative, too small, float, wrong length) start no job;
- an out-of-photo ROI is logged as a failed job;
- source notes in the custody log, the report and the text view;
- parameter round trips, including pre-ROI reports.

The CLI and sidecar tests cover `--roi`, `--source` and the `job.run` ROI schema.

## 3. State of the whole window (what the next person needs)

| PR | Branch | Content | Local gate |
| --- | --- | --- | --- |
| #5 | `m3-minutiae` → `main` | M3 minutiae (review fixed) | passed |
| #6 | `m4-sidecar` → `main` | M4 sidecar, idle lock, unlock rollback, identity/case creation (review fixed) | passed |
| #7 | `m5-validation-metrics` → #6 | `ridge-validate`, NFR-1 baseline (review fixed) | passed |
| #8 | `m5-case-reports` → #7 | FR-28 verified reports, PRIV-3 signed processing record, logged-or-nothing exports (review fixed) | passed |
| #9 | `m5-compare-reproduce` → #8 | FR-52 reference images and comparison sheets, FR-34/NFR-3 `reproduce` | passed |
| #10 | `m5-store-listing` → #9 | `cases` / `store.cases`, `extract --keep-going` | passed |
| (this) | `m5-roi-source` → #10 | proposed FR-35 ROI, FR-21 source note | see PR |

All Codex review threads on #5–#8 were fixed, answered and resolved. Merge in order, retargeting each PR to `main` after the one below it merges.

## 4. Open items

- **GitHub Actions has been blocked since 2026-10-17 at about 09:50+02:00 by a billing or spending-limit problem.** Jobs are not started. The owner must fix this under GitHub *Settings → Billing & plans*. Nothing has been merged since, because the process requires a green CI matrix (3 OS × Python 3.12–3.14, including the arm64 golden checks), which a local Windows gate cannot replace.
- **FR-35** needs product-owner confirmation; it is marked "proposed" in the PRD.
- **GUI (FR-50 to FR-53):** every flow now has a sidecar method. The Tauri shell is still open and needs an owner decision on the native passphrase prompt per OS.
- OQ-4 (exchange format, FR-41), OQ-11 (reference workstation for NFR-1), OQ-15 (casework architectures) and owner names (OQ-10) are unchanged.

## 5. First thing to do

Fix GitHub billing. Re-run CI on #5, and merge #5 → #6 → … → this branch in order once each is green. Then decide on FR-35 and the GUI passphrase prompt.
