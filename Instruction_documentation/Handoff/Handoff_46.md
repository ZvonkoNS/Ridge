# Handoff_46.md

Date/time (ISO 8601 with offset): 2026-10-24T17:10+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 11 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-method-rectify-30` (stacked on `afis-method-frequency-29`; local commit only, nothing pushed)
Base commit: `91ea2e0` (tip of `afis-method-frequency-29`)
Latest commit: see `git log afis-method-rectify-30`

## 1. Scope

Requested change: item 11 of the assessment: an opt-in rectification of the finger pad's curvature before extraction (ADR-014 variant).

Completed work:

- **Rectification (PRD FR-47, `ridge.pipeline.rectify`).** With `MethodOptions(rectify=True)` and a finger located by skin colour, the finger is first rotated upright (the variant implies FR-45's rotation) and then unrolled: the finger's centre line and half-width are read per row from the mask (rows without a usable width take the nearest one's; both smoothed along the finger with a Gaussian of 3 % of its length), each row is treated as a half-circle of that radius, and the pixel at offset x from the centre line moves to the arc length w·asin(x/w), up to a surface angle of 70° where the pad turns away from the camera. The canvas is bounded (50 MP including its two float maps). The pipeline runs on the unrolled canvas; the print location is mapped back row by row through the inverse (`PrintLocation.from_rectified`) and then through the inverse affine, the frame becoming a polygon with 16 points per curved side. `measurements.rectification` records the pad's median half-width and the unrolled angle; the "Variants" line states that the scale holds on the centre line only. CLI `--rectify`; sidecar `options.rectify`; GUI "Rectify pad curvature", with the curved frame drawn on the original.
- **Refactor.** The warps applied before extraction (rotation, rectification) moved out of `extract_fingerprint` into `_canvas` and a `_Canvas` record that maps the location back, keeping the entrypoint near the 50-line standard.
- Incidental: the pinned toolchain's clippy (1.98) flagged `request.steps % 2 == 0` in the sweep command (Handoff_40); replaced by `is_multiple_of(2)`.
- Docs: PRD FR-47; architecture module list and the `print_area` paragraph; CHANGELOG; README; examiner guide.

Out of scope: rectification without a located finger (no width profile); a model of the pad other than a cylinder per row; items 12 to 14.

## 2. Current repository state

Git status summary: committed on `afis-method-rectify-30`.

Recent commits: `91ea2e0` (Handoff_45) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (covered by the ADR-014 exception row of Handoff_43; ADR-014 already lists FR-47).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ADR-014 / forensic standard §13 (method variant, off by default, recorded) | Yes | Default identity guarded by the goldens (`tests/test_characterization.py` passed); half-width, angle and the curved frame recorded | The ADR-014 exception |
| Coding standards (bounded allocation, CWE-789; entrypoint length) | Yes | `MAX_RECTIFIED_PIXELS` with a typed refusal, tested; `_canvas` split | None |
| FR-50 (region review: where the print came from) | Yes | The frame follows the curved mapping back to the photo; the GUI draws any polygon of three or more points | Frame points rounded to whole pixels; the scale of a rectified print is non-uniform away from the centre line, stated in the report and the guide |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none beyond ADR-014.

Steps outside coding work: FQM decision on ADR-014.

## 4. Forensic impact

Output pixels changed: no with the defaults (goldens exact); yes when `rectify` is on (the photo is resampled once, non-uniformly, before extraction), by explicit choice, recorded and labelled unvalidated.

Defaults or recorded parameters changed: none; `options.rectify`, `measurements.rectification` and a many-point `print_area.frame_px` are new recorded forms.

Revalidation decision required / recorded: required before casework use (ADR-014); not recorded. The non-uniform scale of a rectified print matters for any AFIS submission at a nominal resolution: the resolution holds on the centre line only.

Examiner-facing wording changed (checked against forbidden claims): "Rectify pad curvature", "rectified (pad half-width N px, unrolled to 70 deg; the scale holds on the centre line)", the frame legend "(warped: the job rotated the finger upright or unrolled its pad)"; no identification claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/rectify.py` (new) | Width profile, unrolling plan and maps, forward and inverse point mapping |
| `src/ridge/pipeline/options.py`, `src/ridge/pipeline/extract.py`, `src/ridge/pipeline/location.py` | `rectify` option; `_canvas`/`_Canvas`; `from_rectified`, frame polygon |
| `src/ridge/case/jobs.py`, `src/ridge/case/report_lines.py`, `src/ridge/case/cli_extract.py` | Measurement, "Variants" line, `--rectify` |
| `gui/src/ipc/types.ts`, `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/MethodVariants.tsx`, `gui/src/screens/JobSummary.tsx`, `gui/src/components/PrintArea.tsx` | Option, checkbox, summary, curved frame |
| `gui/src-tauri/src/commands/jobs.rs`, `gui/src-tauri/src/commands/case.rs` | `rectify` in the request and tests; clippy fix |
| `tests/test_rectify.py` (new), `tests/test_method_options.py`, `tests/test_case_store.py`, `gui/src/test/params.test.ts` | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md` | Requirements, design, changelog, usage, guide |
| `Instruction_documentation/Handoff/Handoff_46.md` (new) | This handoff |

## 6. Data store, records and formats

Report fields added: `parameters.options.rectify`, `measurements.rectification` (object with `half_width_px` and `max_angle_deg`, or null); `print_area.frame_px` may now hold more than four points. No migration.

## 7. Configuration, keys and CI

None.

## 8. Security

A bounded resampling of an already-decoded image; one more boolean through the validated option object at every boundary. No new trust boundary.

## 9. Tests

Tests added or updated:

- `tests/test_rectify.py` (new): the width profile of an ellipse mask (centre line, half-width at two rows, rows without finger filled, too few rows or an empty mask give None); the unrolling plan (canvas size, median half-width, exact round trip of the point mapping, arc length at 60°, clamping at the 70° limit, the unrolled mask, the canvas bound raises `WorkAreaTooLargeError`); on a synthetic finger with vertical ridges wrapped on a cylinder the default is unchanged and the variant reads the pattern's spacing within 5 % where the default reads the compressed sides, rates the outer thirds over 1.5 times higher in ridge quality, keeps over 10 % more ridge pixels, maps a curved frame and the outline inside the photo, is repeatable, and with the local-frequency variant records an even spacing (range under 1.1, over 1.1 without unrolling); an unlocated finger is left alone; jobs record the rectification, the report names it, the sidecar accepts `options.rectify` and rejects a non-boolean.
- `tests/test_method_options.py`, `tests/test_case_store.py`: the options JSON includes `rectify`; `gui/src/test/params.test.ts`: the option is sent. Rust tests: the field maps through.

Measured on the synthetic cylinder finger, for the record: the outer thirds' mean ridge quality rose from 55 to 105 (of 255), the kept ridge pixels by 16 %, the global spacing estimate from 8.49 to 8.91 px (pattern 9.0 px); with the local-frequency variant the recorded spacing range narrowed from 1.41 to 1.05 (max over min).

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 196 source files
.venv/Scripts/python.exe -m pytest tests/test_rectify.py tests/test_method_options.py tests/test_case_store.py tests/test_upright.py tests/test_print_area.py tests/test_characterization.py -q   # 78 passed, 1 failed in 277 s: the failing test expected -32602 for a non-boolean option where the sidecar returns -32000 (a RidgeError); the expectation was corrected and that test passed alone (1 passed in 12.5 s)
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 33 files, 122 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass, 36 tests
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_45's branch (afis-method-frequency-29, 91ea2e0) in a worktree: python tools/gate.py test   # GATE45_PENDING
```

Determinism and golden results: `tests/test_characterization.py` passed (goldens exact, live v0 identical); the rectified path tested for repeatability.

Tests not run and why: the full `gate.py all` (stack top); this branch's and Handoff_44's full `test` gates (worktree, in turn); the GUI gate's `npm ci`/build steps; Tauri WebDriver E2E (profile exception); Apple-silicon pixel tests of the variant path (on demand).

Required tests still missing: a benchmark of the variant (validation study).

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none (the variant is off). Rollback: revert the commit.

## 11. Open risks and known issues

- A cylinder per row is a crude model of a fingertip; a real pad flattens where it was pressed and the mask's edge is where skin colour ends, not where the pad turns away. The unroll limit of 70° keeps the stretch under 3x; the recorded half-width and the drawn frame make the applied warp reviewable.
- The stretch towards the sides is not uniform, so a rectified print's pixel pitch is nominal only on the centre line; a submission at a stated resolution should say so (the "Variants" line does).

## 12. Recommended next work

Items 12 to 14 of the assessment: the organisational documents (questionnaire for the AFIS team, pilot protocol, capture guidance), then the full gate on the stack top and the closing handoff.

## 13. First thing the next agent/developer should read or do

`docs/adr/ADR-014-opt-in-method-variants.md`, `src/ridge/pipeline/rectify.py`, this branch's `git show --stat`.
