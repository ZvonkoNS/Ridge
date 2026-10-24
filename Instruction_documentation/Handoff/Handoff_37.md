# Handoff_37.md

Date/time (ISO 8601 with offset): 2026-10-24T11:40+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 2 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-scale-reference-21` (stacked on `afis-deps-20`; local commit only, nothing pushed)
Base commit: `fb5261d` (tip of `afis-deps-20`)
Latest commit: see `git log afis-scale-reference-21`

## 1. Scope

Requested change: item 2 of the assessment, with the product owner's instruction of 2026-10-24: "For adding external objects, please add a notification that it is not present and that the investigator should add something like a ruler or that card if possible, if not proceed as is."

Completed work:

- **ID-1 card as a scale reference (PRD FR-31 a, FR-51).** The two calibration points may lie across an ISO/IEC 7810 ID-1 card (bank, ID and driving-licence cards) instead of on a ruler. `ExportOptions.reference` (`ruler`, `id1-long`, `id1-short`) says what the points lie on; for a card the distance in `ruler` must be the standard edge length (85.60 or 53.98 mm), otherwise the job is refused before it starts, so recorded parameters stay self-consistent and nothing is silently replaced. The scale method is `card`, `scale.reference` names the edge, and the uncertainty is the click error plus the card's size tolerance (0.15 %) plus an alignment allowance (2 %, an engineering assumption recorded in code, to be confirmed by validation). CLI `--card long|short X1 Y1 X2 Y2` supplies the standard length itself; the GUI's "Scale reference" group offers the object and fills in the millimetres for a card; sidecar `job.run` takes `reference`; Rust validates it.
- **No-reference notice.** When no reference points are given the job proceeds as before, and the report (`export.scale.notice`), the CLI (`scale notice: ...`), the text and HTML reports ("Scale notice") and the GUI job summary carry a notice that no scale reference was given, that the scale is estimated from the ridge spacing (±15 %), that the investigator should add a ruler or an ID-1 card in the plane of the finger pad if possible (or mark one already in the photo), and that otherwise the estimate stands and should be stated wherever the export is used. The GUI parameter form shows the same hint before a job while fewer than two points are placed.
- **Limits of use.** New optional flag `require_scale_reference` (a ruler or a card satisfies it); `require_ruler` keeps meaning a ruler, and a card scale now deviates from it in plain words.
- Reports before this change have no `reference`; `ridge-case reproduce` rebuilds them as ruler scales.
- Docs: PRD FR-31, FR-51, §12 item 8, R-3; architecture §7.3 (`job.run`), §8.3 (report example and scale paragraph), limits list; CHANGELOG; README; examiner guide.

Out of scope: items 3 to 14; OQ-4; validation of the card allowances (FQM).

## 2. Current repository state

Git status summary: committed on `afis-scale-reference-21`.

Recent commits: `fb5261d` (Handoff_36), `d799929` (Handoff_35) below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (no new standard, dependency or exception; the ISO/IEC 7810 dimensions are facts used as constants, cited in code and PRD).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 7810:2019 (ID-1 card format, 85.60 × 53.98 mm) | Yes (new reference object) | Constants `ID1_LONG_MM`, `ID1_SHORT_MM`, `CARD_EDGE_TOLERANCE_PCT` in `ridge.export.transforms`; distance checked against them | The alignment allowance (2 %) is an engineering assumption, labelled so in code, PRD and reports, to be validated (PRD §12) |
| Forensic standard §7 (scale is an assumption without a reference) | Yes | The notice names the estimate, its uncertainty and what to do; the limits of use can require a reference | None |
| Coding standards (validation at every boundary) | Yes | Kind and distance checked in the library, the job settings, the sidecar and the Rust core; CLI refuses `--ruler` with `--card` and unknown edges | None |
| Forbidden claims | Yes | New wording describes processing and what to do; no identification or validation claim | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: the card allowances (above).

Steps outside coding work: FQM to confirm or replace `CARD_EDGE_TOLERANCE_PCT` and `CARD_ALIGNMENT_PCT` in the validation study and to decide whether cards are accepted in the limits of use (`require_ruler` vs `require_scale_reference`).

## 4. Forensic impact

Output pixels changed: no. The print and both comparison exports are computed as before; a card reference is another way to supply the scale factor, recorded with its method and uncertainty.

Defaults or recorded parameters changed: `parameters.export.reference` is recorded (default `ruler`, so existing ruler jobs reproduce identically); `export.scale.reference` and `export.scale.notice` are new report fields; limits files may carry `require_scale_reference`.

Revalidation decision required / recorded: the card's uncertainty constants need validation before casework; no existing output changed.

Examiner-facing wording changed (checked against forbidden claims): the notice text (report, CLI, GUI, readable reports), the GUI "Scale reference" group and hint, limits-of-use deviation sentence for scale references; none claims identification, matching or validation.

Data classes touched: synthetic data only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/export/transforms.py`, `src/ridge/export/__init__.py` | `ReferenceKind`, ID-1 constants, `scale_from_reference`, `ScaleEstimate.reference`, method `card` |
| `src/ridge/case/export_step.py` | `ExportOptions.reference`, validation, `SCALE_NOTICE` and `reference` in the report's scale section |
| `src/ridge/case/limits.py` | `require_scale_reference` |
| `src/ridge/case/reproduce.py` | Older reports reproduce as ruler scales |
| `src/ridge/sidecar/job_methods.py`, `src/ridge/sidecar/handlers.py` | `job.run` `reference`, validated |
| `src/ridge/case/cli_extract.py` | `--card`, the scale notice line, `_scale_reference` helper |
| `src/ridge/case/report_lines.py`, `src/ridge/case/reports.py`, `src/ridge/case/report_html.py` | Reference object in the export line; "Scale notice" line and row |
| `gui/src/ipc/types.ts`, `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/ReviewPanel.tsx`, `gui/src/screens/JobSummary.tsx`, `gui/src/components/ScaleBar.tsx`, `gui/src/components/Measure.tsx`, `gui/src/dev/preview.ts` | Reference choice, hint, notice, card scale in the scale bar and measure tool |
| `gui/src-tauri/src/commands/jobs.rs` | `reference` in the job request, validated; tests |
| `tests/test_export.py`, `tests/test_case_export.py`, `tests/test_case_reproduce.py`, `tests/test_limits_of_use.py`, `tests/test_sidecar.py`, `gui/src/test/params.test.ts`, `gui/src/test/scale.test.tsx` (new) | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `CHANGELOG.md`, `README.md` | Requirements, design, guide, changelog, usage |
| `Instruction_documentation/Handoff/Handoff_37.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): report fields `parameters.export.reference`, `export.scale.reference`, `export.scale.notice` (all optional for readers; schema id unchanged); `limits-of-use.json` accepts `require_scale_reference`. The custody log's `job.start` parameters carry `reference` through `JobParams.to_json`.

Migrations and recovery notes: none.

Run-record or export format changes: none.

Write paths added or changed: none.

## 7. Configuration, keys and CI

None.

## 8. Security

Decoder, limit or allow-list changes: the reference kind is an allow-list of three values checked in Python (library, job settings, sidecar) and in Rust; the card distance is checked against the standard before any job starts.

Trust-boundary changes: `job.run` gains one string parameter, validated on both sides; the Rust request keeps `deny_unknown_fields` and requires the field (no hidden default on the way).

Threat-model notes: none new.

Open security risks: none.

## 9. Tests

Tests added or updated:

- `tests/test_export.py`: card scales (both edges, uncertainty sum, reference text), the ruler path unchanged, wrong distances and unknown kinds refused, `ScaleEstimate.reference` validated.
- `tests/test_case_export.py`: a card job records method `card`, the edge and no notice; a job without points records the notice; wrong distance, card kind without points and unknown kinds refused before the job starts; CLI `--card` works, prints the notice without a reference, refuses `wide` and `--ruler` with `--card`.
- `tests/test_case_reproduce.py`: parameters round-trip with a card; older reports without `reference` reproduce as ruler scales.
- `tests/test_limits_of_use.py`: `require_scale_reference` accepts a card and names a ridge-period scale; `require_ruler` names a card; a non-boolean flag is refused.
- `tests/test_sidecar.py`: `job.run` with a card reference, an unknown kind refused, the notice without a reference.
- `gui/src/test/params.test.ts`: `reference` sent explicitly; the standard edge length for a card; `gui/src/test/scale.test.tsx` (new): the hint before a job and its absence with two points, the disabled millimetre field, the card scale and uncertainty in `photoScale`, the notice component and the export line with the reference object.
- `gui/src-tauri/src/commands/jobs.rs` tests: the field maps through; an unknown kind is refused.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 173 source files
.venv/Scripts/python.exe -m pytest tests/test_export.py tests/test_case_export.py tests/test_case_reproduce.py tests/test_limits_of_use.py tests/test_sidecar.py tests/test_case_reports.py tests/test_report_html.py tests/test_case_roi.py tests/test_sidecar_gui_methods.py -q
# 192 passed in 169 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 30 files, 114 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass
.venv/Scripts/python.exe tools/gate.py docs   # pass
.venv/Scripts/python.exe tools/gate.py test   # started after the commit; result in the next handoff
```

Determinism and golden results: no pipeline change; `tests/test_characterization.py` is part of the `test` gate run named above.

Tests not run and why: `python tools/gate.py all` on this branch (the code gates above and the `test` gate were run; the full gate runs on the stack top before any merge); the GUI gate's `npm ci`/build steps (unchanged toolchain since Handoff_35's run); Tauri WebDriver E2E (profile exception).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit; reports written with a card reference still verify and render (their `reference` field is simply ignored by older renderers, which show method `card`).

## 11. Open risks and known issues

- The card alignment allowance is a placeholder until validated; a card photographed obliquely or measured corner to corner (ID-1 corners are rounded, radius 3.18 mm) can be off by more than it. The notice and the GUI say "two points across the card".

## 12. Recommended next work

Item 3 of the assessment: TIFF and BMP export conversions with resolution tags, and a note when an export is enlarged beyond the photo's resolution.

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
