# Handoff_39.md

Date/time (ISO 8601 with offset): 2026-10-24T12:00+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 4 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-submission-23` (stacked on `afis-export-formats-22`; local commit only, nothing pushed)
Base commit: `4191f41` (tip of `afis-export-formats-22`)
Latest commit: see `git log afis-submission-23`

## 1. Scope

Requested change: item 4 of the assessment: the record fields an AFIS operator needs beside the image, and a submission cover sheet.

Completed work:

- **Submission record (PRD FR-38, `src/ridge/case/submission.py`).** Every job report carries `submission`: the finger position the examiner states (ANSI/NIST-ITL friction ridge position code 0 unknown to 10, with its name), the submitting agency the examiner states (free text, validated like other text), a fixed impression description (the ANSI/NIST impression code stays with the AFIS operator, OQ-4), and the camera the photo's file names (from the metadata summary, marked unverified). The statements are job parameters (`finger_position`, `source_agency`): CLI `--finger-position`, `--source-agency`; GUI "Submission record" fields; sidecar `job.run`; Rust validates the code (0-10) and the text (≤ 200 printable characters). Older reports reproduce with code 0 and no agency. Text and HTML reports show a "Submission" line.
- **AFIS submission cover sheet (`src/ridge/case/cover_sheet.py`).** `ridge-case report CASE JOB --cover sheet.html`, the GUI's "Save submission cover sheet..." and sidecar `cover.export` write an HTML page like the readable report (escaped, script-free, same CSP, not signed, naming the signed report's SHA-256 and custody head) with the case reference, the job, the submission record, the files to attach (both comparison exports with stored SHA-256 and size, the grayscale one marked recommended), resolution, scale method, reference object and uncertainty, transforms, the scale and resolution notes, the indicative NFIQ 2 score and the limits-of-use outcome. Writing it is logged as `cover.export` with the page's SHA-256; an existing file is never replaced. A report made before FR-38 renders with "not recorded".
- Docs: PRD FR-38; architecture §7.3 (`job.run`, `cover.export`) and §8.3 (report example, paragraph); CHANGELOG; README; examiner guide.

Out of scope: an ANSI/NIST-ITL Type-2/Type-14 record writer (OQ-4); items 5 to 14.

## 2. Current repository state

Git status summary: committed on `afis-submission-23`.

Recent commits: `4191f41` (Handoff_38) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ANSI/NIST-ITL 1-2011 Update 2015 Table 8 / 1-2025 (friction ridge position codes 0-10) | Yes (codes recorded) | `FINGER_POSITIONS` in `ridge.case.submission`, validated at every boundary; `tests/test_submission.py` | The impression type code is not set by Ridge (operator's decision, OQ-4) |
| Forbidden claims (no identification) | Yes | The record's `notice` and the cover sheet say the statements are the examiner's and nothing is an identification; the camera is marked unverified | None |
| FR-36 (metadata not verified) | Yes | `capture_device` is copied from the metadata summary with the note "as the photo's file records it; not verified by Ridge" | None |
| Readable-report security (escaping, CSP, no scripts) | Yes | The cover sheet reuses the report page's CSP and style; tests check escaping, CSP and the absence of scripts | None |
| Coding standards (validation at every boundary, ≤ ~300 lines) | Yes | Python, sidecar and Rust validation; new modules 120 and 150 lines | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the AFIS team confirms which record fields and impression code their intake needs (OQ-4); the DPO may want to review that the source agency text is case data (it is encrypted in reports like the case reference).

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: two new job parameters with defaults (0, none) recorded in every report; a new report section `submission`; a new custody action `cover.export`. Existing jobs reproduce identically.

Revalidation decision required / recorded: not required (no method change).

Examiner-facing wording changed (checked against forbidden claims): "Submission record (your statements, recorded in the report)", the cover sheet's text, the "Submission" report line; each states that the finger position and agency are statements and the camera is unverified; nothing claims identification.

Data classes touched: synthetic only. The source agency is personal data by reference at most (an organisation name) and lives in the encrypted report like the case reference.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/case/submission.py` (new) | Codes, validation, `Submission`, `submission_record`, `submission_line` |
| `src/ridge/case/cover_sheet.py` (new) | `render_cover_sheet`, `export_cover_sheet` (logged) |
| `src/ridge/case/jobs.py` | `JobParams.finger_position`, `source_agency`, `submission()`; the report section |
| `src/ridge/case/reproduce.py` | Older reports rebuild with the defaults |
| `src/ridge/sidecar/job_methods.py`, `src/ridge/sidecar/handlers.py` | `job.run` fields and summary, `cover.export` |
| `src/ridge/case/cli_extract.py`, `src/ridge/case/cli_records.py` | `--finger-position`, `--source-agency`, `report --cover` |
| `src/ridge/case/reports.py`, `src/ridge/case/report_html.py` | "Submission" line and row |
| `gui/src/ipc/types.ts`, `gui/src/ipc/commands.ts`, `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/JobSummary.tsx`, `gui/src/screens/JobsSection.tsx`, `gui/src/dev/preview.ts` | Form fields, summary line, cover sheet button, dev preview route |
| `gui/src-tauri/src/commands/jobs.rs`, `gui/src-tauri/src/commands/records.rs`, `gui/src-tauri/src/commands/list.rs`, `gui/src-tauri/src/lib.rs`, `gui/src-tauri/capabilities/main.json` | Request fields validated; `export_cover` command registered and allowed |
| `tests/test_submission.py` (new), `tests/test_case_store.py`, `gui/src/test/params.test.ts`, `gui/src/test/submission.test.tsx` (new), `gui/src/test/scale.test.tsx` | Tests (section 9); the scale test now finds its select by label (two selects exist) |
| `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `CHANGELOG.md`, `README.md` | Requirements, design, guide, changelog, usage |
| `Instruction_documentation/Handoff/Handoff_39.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): report section `submission` and parameters `finger_position`, `source_agency` (schema id unchanged; readers treat them as optional); custody action `cover.export` (`job_id`, `sha256` of the page, `destination`).

Migrations and recovery notes: none.

Run-record or export format changes: a new export document kind (the cover sheet, HTML, not signed), like the readable report.

Write paths added or changed: the cover sheet is written through `publish_logged` to an examiner-chosen path, like the readable report.

## 7. Configuration, keys and CI

None.

## 8. Security

Decoder, limit or allow-list changes: none; two new inputs (a code and a text) validated in Python, the sidecar and Rust.

Trust-boundary changes: one new Tauri command (`export_cover`) in the allow-list and capability, mapping to one sidecar method; the save dialog chooses the path.

Threat-model notes: the cover sheet shows report values only, escaped, under the report page's CSP; it embeds no images and copies no metadata beyond the camera name already in the report.

Open security risks: none.

## 9. Tests

Tests added or updated:

- `tests/test_submission.py` (new): code and text validation; the record's content and notes; jobs record the statements and reports render them; older parameter sets rebuild with defaults; an out-of-range code is refused before the job starts; the camera comes from the photo's metadata; the cover sheet lists both exports with hashes, the record, the scale notice, has a CSP and no script, is logged as `cover.export`, refuses an existing file, and renders older reports with "not recorded"; CLI `--finger-position`/`--source-agency`/`report --cover`; sidecar `job.run` with the fields and `cover.export`.
- `tests/test_case_store.py`: the full parameter assertion includes the two new fields.
- `gui/src/test/params.test.ts`: the fields are sent, trimmed and bounded; `gui/src/test/submission.test.tsx` (new): the form offers the eleven codes and the agency field; the summary line wording. Rust tests: fields map through; code 11 and a 201-character agency are refused.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 180 source files
.venv/Scripts/python.exe -m pytest tests/test_submission.py tests/test_case_store.py tests/test_case_export.py tests/test_case_reproduce.py tests/test_sidecar.py tests/test_case_reports.py tests/test_report_html.py tests/test_case_cli.py -q
# 126 passed in 281 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 31 files, 117 tests passed after the scale test fix
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass
.venv/Scripts/python.exe tools/gate.py docs   # pass
.venv/Scripts/python.exe tools/gate.py test   # Handoff_38's run (branch afis-export-formats-22, in a worktree) and this branch's run: results in the next handoff
```

Determinism and golden results: no pipeline change.

Tests not run and why: the full `gate.py all` (stack top); the GUI gate's `npm ci`/build steps (toolchain unchanged); Tauri WebDriver E2E (profile exception).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit; reports with a `submission` section still verify (the renderers ignore unknown keys).

## 11. Open risks and known issues

- The impression type and the exact record layout the AFIS needs are unknown until OQ-4 is answered; the cover sheet and the record give the operator the facts in words rather than in a vendor format.

## 12. Recommended next work

Item 5 of the assessment: the scale sweep export.

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
