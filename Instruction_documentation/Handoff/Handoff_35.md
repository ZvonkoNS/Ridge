# Handoff_35.md

Date/time (ISO 8601 with offset): 2026-10-24T11:00+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window granted by the product owner on 2026-10-24 ("implement all of them one by one. Make sure to adhere to coding standards in this project and refactoring. For adding external objects, please add a notification that it is not present and that the investigator should add something like a ruler or that card if possible, if not proceed as is."), item 1 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-gray-export-19` (stacked on `main`; local commits only, nothing pushed, no pull request opened)
Base commit: `dc66a41` (tip of `main`, merge of PR #32)
Latest commit: see `git log afis-gray-export-19`

## 1. Scope

Requested change: On 2026-10-24 the product owner asked what could raise the quality of Ridge's results and the chance that its exports are usable in NAFIS/AFIS workflows. The assessment named 14 items: six additive engineering changes, four opt-in method changes, and four organisational items. The owner then asked to implement all of them one by one, in the project's coding standards, with a refactoring pass, and with a notification whenever a scale reference object (ruler or card) is missing from a photo so that the investigator can add one if possible and otherwise proceed as is.

This handoff covers **item 1: the grayscale comparison export** (PRD FR-37). Each following item gets its own stacked branch and handoff.

Completed work:

- The pipeline renders the same window of the Gabor-filtered ridge signal twice: thresholded (the print, exactly as v0 made it; `binarize` moved unchanged into the new `src/ridge/pipeline/render.py`) and through a soft contrast curve (`render_gray`): the algebraic sigmoid x / sqrt(1 + x²) with gain 0.5, faded to zero at the print's edge (the region map's 0.5 level). `ExtractionResult.gray` carries it; `crop=False` frames it like the print.
- `make_comparison_export(..., tone="grayscale")` applies the same polarity, mirror and scale transforms to it (`tone:grayscale` first), so both exports have identical geometry.
- Every job stores the grayscale export as role `export-gray` (label `*_comparison_gray_<ppi>ppi.png`), names it in the report under `export.grayscale`, and computes NFIQ 2 on it; `quality.nfiq2.image` says which image was scored.
- `ridge-case compare` accepts either export; `ridge-case export-all --role export-gray` exports the grayscale ones; the text and HTML reports name the twin and the scored image.
- GUI: the new output is shown first after a job, labelled "Grayscale comparison export" (processed-image warning included), accepted by the References sheet, the minutiae overlay and the measure tool; Inventory offers "Export all N grayscale exports..."; the dev preview has one.
- Docs: PRD FR-37 (new) and FR-33 (NFIQ 2 on the grayscale export), architecture §7.2, §8.3 and the module list, CHANGELOG, README, standards profile.

Out of scope: items 2 to 14 of the assessment (next branches); merging or pushing (the owner decides); the dev-dependency advisories found by the gates (section 9; fixed on the next branch).

## 2. Current repository state

Git status summary: committed on `afis-gray-export-19`; `main` untouched.

Recent commits: `dc66a41` Merge pull request #32 (`main`); this branch adds one commit for item 1.

## 3. Standards applicability and evidence

Project standards profile updated: yes (`Last verified` 2026-10-24; the ISO/IEC 29794-4 row notes that NFIQ 2 now scores the grayscale export).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 39794-4 / 19794-4 (finger image: 8-bit grayscale representation) | Yes | The grayscale export is 8-bit grayscale at 500 ppi with dark ridges, the representation these formats and AFIS feature extractors expect; the container stays PNG (OQ-4) | None |
| ISO/IEC 29794-4 / NFIQ 2 | Yes | NFIQ 2 is computed on the grayscale export, the kind of image the metric is defined on; still indicative only (photo-derived) | Existing profile exception (NFIQ 2 on photo-derived images) unchanged |
| Forensic standard §6 (method constants), ADR-009 (per-architecture reproducibility) | Yes | `GRAY_GAIN` and `PRINT_EDGE` named in one module; the curve uses IEEE 754 arithmetic only (no libm), `tests/test_render.py` checks determinism | None |
| Coding standards (≤ ~300 lines, docstrings, typing, lint) | Yes | `render.py` 70 lines; `extract.py` shrank; ruff, ruff format and mypy strict clean | None |
| Data minimisation (FR-12) | Yes | The new PNG carries only IHDR, pHYs, IDAT, IEND (same encoder as the binary export) | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps:

- The grayscale export is a new output and must be covered by the method validation (forensic standard §13) before casework; the Forensic Quality Manager should decide whether the matcher benchmark (PRD §12) runs on the grayscale export (recommended), the binary one, or both.

Steps outside coding work (validation, DPIA, legal, owner approvals):

- FQM: include the grayscale export in the validation plan; decide which export the AFIS pilot uses.

## 4. Forensic impact

Output pixels changed: **no** for the print, the debug images and the binary comparison export (golden characterization and the live-v0 comparison passed; `tests/test_characterization.py`). **A new output is added**: the grayscale comparison export (role `export-gray`). It is derived from the same filter output and region as the print, so it shows no ridge the print does not show; it adds the ridge strength the threshold discards.

Defaults or recorded parameters changed: no parameter changed. Reports gain `export.grayscale` and `quality.nfiq2.image`; NFIQ 2 is now computed on the grayscale export instead of the binary one (FR-33), so scores are not comparable with scores from earlier reports (which did not name their image).

Revalidation decision required / recorded: required for casework use of the grayscale export (new output); not recorded. No existing output changed.

Examiner-facing wording changed (checked against forbidden claims): new labels "Grayscale comparison export", "grayscale twin", "on the export-gray image"; no identification, matching or validation claim; the processed-image warning applies to the new role.

Data classes touched and how class E data stayed out of repository and agent session: synthetic images only (`tests/synthetic.py`); no real photo was requested, opened or produced.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/render.py` (new) | `binarize` (moved from `extract.py`, unchanged ops) and `render_gray`; method constants `GRAY_GAIN`, `PRINT_EDGE` |
| `src/ridge/pipeline/extract.py` | `_render` resizes once and calls both renderings; `_framed` for `crop=False`; `ExtractionResult.gray` |
| `src/ridge/export/transforms.py`, `src/ridge/export/__init__.py` | `tone` argument (`Tone`, `TONES`, `TONE_GRAYSCALE`) on `make_comparison_export` |
| `src/ridge/case/export_step.py` | Stores both exports, `export.grayscale`, NFIQ 2 on the grayscale export with `image` recorded; `_scale_info` split out |
| `src/ridge/case/case_model.py`, `src/ridge/case/export_all.py`, `src/ridge/case/compare.py` | Role `export-gray` stored, exportable in bulk and accepted on comparison sheets |
| `src/ridge/case/report_lines.py` | Export line names the grayscale twin; NFIQ 2 line names the scored image |
| `gui/src/ipc/types.ts`, `gui/src/components/ExhibitLabel.tsx`, `gui/src/components/MinutiaeToggle.tsx`, `gui/src/lib/minutiae.ts`, `gui/src/screens/ReviewPanel.tsx`, `gui/src/screens/ReferencesSection.tsx`, `gui/src/screens/Inventory.tsx`, `gui/src/screens/JobSummary.tsx`, `gui/src/dev/preview.ts` | The new role in the GUI (label, preferred output, overlay, sheet, bulk export, summary lines, dev preview) |
| `gui/src-tauri/src/commands/case.rs` | `export-gray` in the bulk-export role allow-list |
| `tests/test_render.py` (new), `tests/test_export.py`, `tests/test_case_export.py`, `tests/test_case_compare.py`, `tests/test_case_store.py`, `tests/test_sidecar.py` | Tests (section 9) |
| `gui/src/test/grayexport.test.tsx` (new), `gui/src/test/labels.test.tsx` | GUI tests |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `Instruction_documentation/Project_Standards_Profile.md` | FR-37, FR-33, §7.2, §8.3, module list, changelog, usage, profile date |
| `Instruction_documentation/Handoff/Handoff_35.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): new stored role `export-gray` (folder `artefacts/`, same sealing and custody entries as `export`). Job reports (`ridge.job-report/1`, unchanged schema id) gain `export.grayscale {sha256, transforms}` and `quality.nfiq2.image`; readers treat both as optional (older reports render as before, tested).

Migrations and recovery notes: none needed. Existing stores hold no `export-gray` items; new jobs add them. A Ridge version older than this one does not know the role and would refuse to list a store that holds one (forward compatibility only; no such mixed deployment is planned).

Run-record or export format changes: none (PNG with pHYs, as the binary export).

Write paths added or changed (update `direct_mutation_authorization_audit.md`): none; the grayscale export goes through `OpenCase.store_artefact` and the existing export paths.

## 7. Configuration, keys and CI

New or changed configuration keys or `RIDGE_*` variables: none.

Key-custody or signing changes: none.

CI workflow, permissions or action-pin changes: none.

## 8. Security

Decoder, limit or allow-list changes: none (the new PNG is encoded by the same `encode_png`; the GUI's bulk-export allow-list gains the new role in Rust and in the sidecar).

Trust-boundary changes (sidecar, IPC, capabilities, CSP): none; `job.run` returns the same summary fields, with the new sub-object inside `export`.

Threat-model notes: no new input is parsed; no new write path.

Open security risks: none from this change.

## 9. Tests

Tests added or updated:

- `tests/test_render.py` (new): the curve is zero outside the print's region and fades in, monotone, mid-grey at zero signal, flip mirrors it; `binarize` keeps the v0 rules and refuses an empty region; the pipeline's grayscale twin has the print's shape, is brighter on ridges, lies within two ridge spacings of the print's ridges, is deterministic, and is framed like the print with `crop=False`.
- `tests/test_export.py`: the grayscale export equals the library's transforms on `result.gray`, shares geometry and factor with the binary export, is darkest where the binary export has ridges; a result without `gray` or an unknown tone is refused.
- `tests/test_case_export.py`: the job stores `export-gray`, records `export.grayscale`, and a hashing fake NFIQ 2 proves the tool received the grayscale export; the not-configured case records the image too.
- `tests/test_case_compare.py`: a sheet from the grayscale export; `tests/test_case_store.py`, `tests/test_sidecar.py`: output role sets and counts.
- `gui/src/test/grayexport.test.tsx` (new): role name, export line with and without the twin, export-space minutiae for the new role; `labels.test.tsx`: processed-image warning on the new role.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools            # All checks passed!
.venv/Scripts/python.exe -m ruff format --check src tests tools   # 172 files already formatted
.venv/Scripts/python.exe -m mypy                                  # Success: no issues found in 173 source files
.venv/Scripts/python.exe tools/gate.py all
# docs, lint, format, typecheck: pass
# test: 888 passed, 3 skipped (POSIX permission bits) in 681 s; coverage 96.81 % (fail-under 90)
# sast: pass
# deps: FAILED on requirements-dev.lock only: filelock 4.2.0 (CVE-2026-112906 and five more, fix 4.2.1),
#       setuptools 84.0.0 (GHSA-xmj3-9gf7-h52w, fix 84.1.0); requirements.lock: no known vulnerabilities.
#       These advisories were published after Handoff_31's audit and are unrelated to this change
#       (the locks were not touched); fixed on the next branch (afis-deps-20).
.venv/Scripts/python.exe tools/gate.py secrets licenses sbom gui
# secrets, licenses, sbom: pass
# gui: npm ci, lint, typecheck, prettier, vitest (110 tests, 29 files), build, preview-absent: pass;
#      npm audit --audit-level=moderate: FAILED on the transitive development package fast-uri 3.0.0-3.1.8
#      (GHSA-w74x-v6f9-j3xg and three more, moderate; fix available). Published after the last audit;
#      unrelated to this change; fixed on the next branch.
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked
# pass (run separately because the GUI gate stopped at npm audit)
cd gui/src-tauri && cargo audit --deny warnings && cargo deny --locked check   # see the commit message / next handoff for the result
```

Determinism and golden results: `tests/test_characterization.py` passed (stored per-architecture goldens and the live v0 run); the print and debug images are bit-identical; `tests/test_render.py` runs the pipeline twice and compares the grayscale twin exactly.

Tests not run and why: the full CI matrix (on-demand only, owner decision); Tauri WebDriver E2E (profile exception); the GUI gate's cargo audit/deny/SBOM steps inside the gate (stopped at npm audit; cargo audit and deny were run separately, see above); NFIQ 2 with the real NIST tool (not installed on this workstation; a fake tool stands in).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build

Ready: not alone; the branch is one of a stack. Gates pass except the two dependency advisories above, which the next branch fixes.

Blockers: owner review of the stack; the two lock upgrades.

Rollback or mitigation: revert the commit; stores keep any `export-gray` items already written (they are ordinary artefacts; an older Ridge would not know the role, see section 6).

## 11. Open risks and known issues

- The grayscale export is unvalidated like every other output; it must not be described as improving identification. Validation decides whether it helps matchers (that is the hypothesis behind item 1).
- NFIQ 2 scores from before and after this change are not comparable (different image scored); reports name the image from now on.

## 12. Recommended next work

The assessment's items, in the order they will be implemented on stacked branches:

1. Grayscale comparison export: **this branch**.
2. Scale reference: ISO/IEC 7810 ID-1 card edges as a reference object, the no-reference notice (report, CLI, GUI), `require_scale_reference` in the limits of use.
3. TIFF and BMP export conversions with resolution tags; a note when an export is enlarged beyond the photo's resolution.
4. Submission record fields (finger position, source agency, capture device) and an AFIS submission cover sheet.
5. Scale sweep export for uncertain scales.
6. Provenance hints (recompression, missing EXIF, estimated JPEG quality).
7. Identification-mode metrics (rank-k hit rate, CMC) in `ridge-validate`.
8. Opt-in specular-highlight mask and measured channel choice (method change, ADR, off by default).
9. Opt-in rotation to upright (method change, ADR, off by default).
10. Opt-in local ridge-frequency map and multi-frequency Gabor bank (method change, ADR, off by default).
11. Opt-in curvature rectification (method change, ADR, off by default).
12. Organisational items (OQ-4 questionnaire for the AFIS team, pilot protocol, capture guidance): documents.

## 13. First thing the next agent/developer should read or do

Read this handoff and `git log main..afis-gray-export-19`; then the handoffs of the following branches in order. Run `python tools/gate.py all` on the stack top before proposing a merge.
