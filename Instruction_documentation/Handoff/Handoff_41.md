# Handoff_41.md

Date/time (ISO 8601 with offset): 2026-10-24T12:30+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 6 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-provenance-25` (stacked on `afis-sweep-24`; local commit only, nothing pushed)
Base commit: `89959e0` (tip of `afis-sweep-24`)
Latest commit: see `git log afis-provenance-25`

## 1. Scope

Requested change: item 6 of the assessment: provenance hints so that forwarded or edited copies are noticed and the original file is requested.

Completed work:

- **Provenance hints (PRD FR-42, `src/ridge/metadata/provenance.py`).** From the metadata record (FR-36) and the file's encoding, Ridge derives short display-safe hints that a photo may be a copy or an edit rather than the camera's original: no EXIF block; an EXIF block without a camera; the software the file names; a longest side typical of messaging-app and web copies when no EXIF is present; an XMP edit history; an approximate JPEG quality estimated from the luminance quantisation table (the table's sum relative to the ITU-T T.81 Annex K table, independent of coefficient order); a format phones do not save photos in (PNG, BMP, WebP). The record (`ridge.provenance-hints/1`) carries the hints, the quality estimate and a notice that Ridge verifies none of them, that none proves how the photo was handled, and that the original file from the device extraction should be requested when a copy is suspected. Nothing is scored or concluded.
- Recorded in every job report as `input.provenance`; shown in the text and HTML reports after the metadata, by `ridge-case metadata` (the `--json` output stays the metadata record alone), by sidecar `metadata.get` (`provenance`) and in the GUI's metadata panel (photo and report views). The CLI and sidecar read the photo once for both the record and the hints (`read_photo_record`).
- Docs: PRD FR-42; architecture §7.3 (`metadata.get`) and §8.3 paragraph; CHANGELOG; examiner guide.

Out of scope: error-level analysis or double-compression detection (research methods, not hints); items 7 to 14.

## 2. Current repository state

Git status summary: committed on `afis-provenance-25`.

Recent commits: `89959e0` (Handoff_40) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ITU-T T.81 (JPEG) Annex K Table K.1, IJG quality scaling | Yes (quality estimate) | `STD_LUMINANCE` and the sum-ratio estimate in code; `tests/test_provenance.py` checks estimates within 2 of the saving quality for 95, 85, 75 and 50 | The estimate is labelled approximate; non-IJG encoders give an estimate that is only indicative |
| FR-36 (metadata not verified) and R-13 | Yes | Every hint and the record's notice say Ridge verifies nothing; the examiner guide repeats it | None |
| CWE-150 display safety | Yes | Hint text passes through the metadata reader's `text()`; a Software tag with a terminal escape is shown as `<U+001B>` (tested) | None |
| Coding standards (bounded, pure, ≤ ~300 lines) | Yes | The header read is Pillow's bounded open on allow-listed formats; eight fixed hint kinds; module 170 lines | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: none; the DPO may note that hints are derived data about the file, not about a person.

## 4. Forensic impact

Output pixels changed: no.

Defaults or recorded parameters changed: none. Reports gain `input.provenance`.

Revalidation decision required / recorded: not required (no method change).

Examiner-facing wording changed (checked against forbidden claims): the hint sentences, the notice and the GUI block; each is phrased as a hint and none claims what happened to the photo.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/metadata/provenance.py` (new) | Hints, quality estimate, text lines |
| `src/ridge/case/jobs.py` | `input.provenance` in the report |
| `src/ridge/case/photo_metadata.py`, `src/ridge/case/cli_metadata.py`, `src/ridge/sidecar/case_methods.py` | One read for record and hints; CLI and sidecar output |
| `src/ridge/case/reports.py`, `src/ridge/case/metadata_render.py`, `src/ridge/case/report_html.py` | Text and HTML rendering |
| `gui/src/ipc/types.ts`, `gui/src/lib/usePhotoMetadata.ts`, `gui/src/components/PhotoMetadata.tsx`, `gui/src/screens/JobsSection.tsx` | The hints block under the metadata (photo and report views) |
| `tests/test_provenance.py` (new), `gui/src/test/provenance.test.tsx` (new) | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `CHANGELOG.md` | Requirements, design, guide, changelog |
| `Instruction_documentation/Handoff/Handoff_41.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): report field `input.provenance` (optional for readers). `metadata.get` returns `provenance` beside `metadata`.

Migrations and recovery notes: none.

Run-record or export format changes: none.

Write paths added or changed: none.

## 7. Configuration, keys and CI

None.

## 8. Security

Decoder, limit or allow-list changes: the header read reuses Pillow with the allow-list and reads the JPEG quantisation tables Pillow already parsed; failures give no hints rather than an error.

Trust-boundary changes: `metadata.get` returns one more object built by the trusted core from safe text.

Threat-model notes: hint text is built by Ridge; the only embedded value (the Software tag) comes through the metadata reader's display-safe path and is passed through it again.

Open security risks: none.

## 9. Tests

Tests added or updated:

- `tests/test_provenance.py` (new): the quality estimate against JPEGs saved at known qualities and its refusals; a stripped 1280-px JPEG reads as no EXIF, copy size and quality; a camera JPEG names its software and history and gets no missing-EXIF hint; an EXIF block without a camera; a PNG photo; bytes that are not an image give bounded hints without raising; a terminal escape in the Software tag is shown as `<U+001B>`; jobs record the hints and both report renderers show them, older reports show nothing; `ridge-case metadata` prints them from one logged read and `--json` stays the metadata record; sidecar `metadata.get` returns them.
- `gui/src/test/provenance.test.tsx` (new): the hints list with its notice, the no-hint wording, nothing for older reports.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 186 source files
.venv/Scripts/python.exe -m pytest tests/test_provenance.py tests/test_metadata_cli.py tests/test_metadata_reports.py tests/test_case_reports.py tests/test_report_html.py tests/test_sidecar_gui_methods.py -q
# 61 passed in 113 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 33 files, 121 tests passed
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_39's branch (afis-submission-23, commit f98ad18) in a worktree: python tools/gate.py test (running; result in the next handoff)
```

Determinism and golden results: no pipeline change.

Tests not run and why: the full `gate.py all` (stack top); this branch's and the sweep branch's full `test` gate (worktree runs in turn); Rust checks (no Rust change on this branch); Tauri WebDriver E2E (profile exception).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit; reports with `input.provenance` still verify and render (unknown keys are ignored by older renderers).

## 11. Open risks and known issues

- The quality estimate assumes an IJG-scaled table; encoders with their own tables (some phone pipelines) give a value that is only indicative, which the text says.

## 12. Recommended next work

Item 7 of the assessment: identification-mode metrics (rank-k hit rate, CMC) in `ridge-validate`.

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
