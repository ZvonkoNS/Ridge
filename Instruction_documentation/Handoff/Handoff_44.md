# Handoff_44.md

Date/time (ISO 8601 with offset): 2026-10-24T13:30+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 9 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-method-upright-28` (stacked on `afis-method-channel-27`; local commit only, nothing pushed)
Base commit: `f45abb5` (tip of `afis-method-channel-27`)
Latest commit: see `git log afis-method-upright-28`

## 1. Scope

Requested change: item 9 of the assessment: an opt-in rotation of the finger to upright before extraction (ADR-014 variant).

Completed work:

- **Upright rotation (PRD FR-45, `ridge.pipeline.upright`).** With `MethodOptions(upright=True)` and a finger located by skin colour, the finger's axis is taken from the mask's second moments and the tip from the narrower end (a fingertip tapers); when both ends are alike, the end farther from the photo's border is the tip, and when that is a tie too, the smaller turn wins. The photo is rotated once (bilinear) and the mask with it (nearest) onto a canvas that holds the whole photo (bounded at 250 MP), the pipeline runs on the canvas, and the print location is mapped back to the photo through the inverse affine: `print_area.frame_px` holds the tilted frame's corners, `box_px` their bounds, `rotation_deg` the turn; `measurements.upright_rotation_deg` records it (null when the finger was not located and nothing was rotated). CLI `--upright`; sidecar `options.upright`; GUI "Rotate to upright", which also draws the tilted frame on the original and names the turn in the summary and the area line.
- Docs: PRD FR-45; architecture module list and the `print_area` paragraph; CHANGELOG; README; examiner guide.

Out of scope: rotation without a located finger (no axis to measure); items 10 to 14.

## 2. Current repository state

Git status summary: committed on `afis-method-upright-28`.

Recent commits: `f45abb5` (Handoff_43) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (covered by the ADR-014 exception row of Handoff_43).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ADR-014 / forensic standard §13 (method variant, off by default, recorded) | Yes | Default-identity guarded by the goldens (`tests/test_characterization.py` passed); the rotation and the tilted frame recorded in the report | The ADR-014 exception |
| Coding standards (bounded allocation, CWE-789) | Yes | The rotated canvas is bounded (`MAX_ROTATED_PIXELS`) with a typed refusal | None |
| FR-50 (region review: where the print came from) | Yes | The location stays in the photo's pixels through the inverse mapping; the GUI draws the tilted frame | Corner coordinates are rounded to whole pixels (stated in the architecture) |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none beyond ADR-014.

Steps outside coding work: FQM decision on ADR-014.

## 4. Forensic impact

Output pixels changed: no with the defaults (goldens exact); yes when `upright` is on (the photo is resampled once before extraction), by explicit choice, recorded and labelled unvalidated.

Defaults or recorded parameters changed: none; `options.upright`, `measurements.upright_rotation_deg`, `print_area.frame_px` and `print_area.rotation_deg` are new recorded fields.

Revalidation decision required / recorded: required before casework use (ADR-014); not recorded.

Examiner-facing wording changed (checked against forbidden claims): "Rotate to upright", "rotated N° to upright", the tilted-frame legend; no identification claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/upright.py` (new) | Axis, tip, rotation, canvas, inverse mapping |
| `src/ridge/pipeline/options.py`, `src/ridge/pipeline/extract.py`, `src/ridge/pipeline/location.py` | `upright` option; rotation in the pipeline; `frame`/`rotation_deg` and `in_photo` on the location |
| `src/ridge/case/jobs.py`, `src/ridge/case/report_lines.py`, `src/ridge/case/cli_extract.py` | Measurement, "Variants" line, `--upright` |
| `gui/src/ipc/types.ts`, `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/JobSummary.tsx`, `gui/src/components/PrintArea.tsx` | Option, summary helper `variantsLine`, tilted frame and legend |
| `gui/src-tauri/src/commands/jobs.rs` | `upright` in the request; tests |
| `tests/test_upright.py` (new), `tests/test_method_options.py`, `tests/test_case_store.py`, `gui/src/test/params.test.ts` | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md` | Requirements, design, changelog, usage, guide |
| `Instruction_documentation/Handoff/Handoff_44.md` (new) | This handoff |

## 6. Data store, records and formats

Report fields added: `parameters.options.upright`, `measurements.upright_rotation_deg`, `measurements.print_area.frame_px` and `.rotation_deg` (only when rotated). No migration.

## 7. Configuration, keys and CI

None.

## 8. Security

A bounded rotation of an already-decoded image; one more boolean through the validated option object at every boundary. No new trust boundary.

## 9. Tests

Tests added or updated:

- `tests/test_upright.py` (new): axis and tip from a tapered mask (upright, flipped, turned by 40°, −75° and 120°: the rotation brings the axis back to vertical with the tip up); symmetric and degenerate masks (vertical ellipse barely turns, horizontal ellipse turns 90°, empty and tiny masks give no rotation); a whorl photo turned by 30° extracts with `upright` to a print within 10 % of the untouched size, with the rotation within 3° of −30°, frame and outline inside the photo, deterministically; an upright photo turns by less than 0.5°; an unlocated finger is left alone and the plain record keeps no frame; the inverse mapping inverts the canvas mapping; jobs record the rotation, the "Variants" line names it, the sidecar accepts and validates `options.upright`.
- `tests/test_method_options.py`, `tests/test_case_store.py`: the options JSON includes `upright`; `gui/src/test/params.test.ts`: the option is sent. Rust tests: the field maps through.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 191 source files
.venv/Scripts/python.exe -m pytest tests/test_upright.py tests/test_method_options.py tests/test_print_area.py tests/test_characterization.py tests/test_case_store.py -q   # 74 passed in 205 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 33 files, 122 tests passed (then the overlay lint fix re-checked with lint, typecheck and the two affected test files)
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_43's branch (afis-method-channel-27, f45abb5) in a worktree: python tools/gate.py test (running; result in the next handoff)
```

Determinism and golden results: `tests/test_characterization.py` passed (goldens exact, live v0 identical); the upright path tested for repeatability.

Tests not run and why: the full `gate.py all` (stack top); this branch's full `test` gate (worktree, in turn); the GUI gate's `npm ci`/build steps; Tauri WebDriver E2E (profile exception); Apple-silicon pixel tests of the variant path (on demand).

Required tests still missing: a benchmark of the variant (validation study).

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none (the variant is off). Rollback: revert the commit.

## 11. Open risks and known issues

- The tip heuristic can be wrong on a finger photographed with the hand in view (the hand end is wider, so that is handled, but a cropped photo showing only a straight segment is a tie resolved by border distance); the report always records the turn and the GUI shows the frame, so a wrong turn is visible.

## 12. Recommended next work

Item 10 of the assessment: opt-in local ridge-frequency map with a multi-frequency Gabor bank (ADR-014 variant).

## 13. First thing the next agent/developer should read or do

`docs/adr/ADR-014-opt-in-method-variants.md`, Handoff_35 section 12, this branch's `git show --stat`.
