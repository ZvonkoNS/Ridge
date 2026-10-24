# Handoff_45.md

Date/time (ISO 8601 with offset): 2026-10-24T15:40+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 10 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-method-frequency-29` (stacked on `afis-method-upright-28`; local commit only, nothing pushed)
Base commit: `3fbbf94` (tip of `afis-method-upright-28`)
Latest commit: see `git log afis-method-frequency-29`

## 1. Scope

Requested change: item 10 of the assessment: an opt-in local ridge-frequency map with a multi-frequency Gabor bank (ADR-014 variant).

Completed work:

- **Local ridge frequency (PRD FR-46, `ridge.pipeline.frequency`).** With `MethodOptions(local_frequency=True)` the ridge spacing is measured in 64 px blocks every 16 px at working scale with the same patch-spectrum method as the global estimate (Hanning window, 256-point FFT, 1/f² whitening, the peak inside 0.70 to 1.68 of the nominal spacing). Blocks reaching outside the finger are not measured and blocks whose spectral peak is less than half as sharp as the typical block are not trusted; both are filled from their measured neighbours (normalised convolution, two cells reach; the nominal spacing where no measured block is near). The grid is median-filtered, smoothed, clamped and spread over the image with each cell at its block centre. Each pixel is then filtered with the Gabor bank tuned to its own spacing by interpolating (in log spacing) between the two nearest of six banks at 0.70, 0.84, 1.0, 1.19, 1.42 and 1.68 of the nominal; banks no pixel asks for are skipped. Periodicity is checked one local spacing ahead and behind; the bank power becomes a per-pixel map. The range of spacings used inside the print is recorded as `measurements.local_period_px` (min, median, max in photo pixels) and named in the "Variants" line of the report and the GUI summary. CLI `--local-frequency`; sidecar `options.local_frequency`; GUI "Local ridge frequency".
- **Refactor for the file-length standard.** The enhancement step (contrast normalisation, Gabor filtering, ridge quality, print region, and now the local-frequency path) moved from `ridge.pipeline.extract` (314 lines) to the new `ridge.pipeline.enhance` (77 lines; `extract.py` is 253 lines). `WORK_PERIOD` now lives there and `ridge.pipeline` re-exports it as before. The GUI's method-variants fieldset moved from `ParametersForm.tsx` (470 lines) to `MethodVariants.tsx`, with the shared checkbox in `components/Check.tsx` (the form is 390 lines). Pure moves; the goldens stayed exact.
- Docs: PRD FR-46; architecture module list; CHANGELOG; README; examiner guide.
- Incidental: `cargo fmt` rewrapped one call in `gui/src-tauri/src/commands/case.rs` (the sweep dialog line of Handoff_40); no behaviour change.

Out of scope: items 11 to 14; a benchmark of the variant.

## 2. Current repository state

Git status summary: committed on `afis-method-frequency-29`.

Recent commits: `3fbbf94` (Handoff_44) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (covered by the ADR-014 exception row of Handoff_43; ADR-014 already lists FR-46).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ADR-014 / forensic standard §13 (method variant, off by default, recorded) | Yes | Default identity guarded by the goldens (`tests/test_characterization.py` passed after the refactor); the spacing range recorded in the report | The ADR-014 exception |
| Coding standards (files ≈300 lines, pure pipeline, bounded work) | Yes | `enhance.py` and `MethodVariants.tsx` splits; the map is computed on the already bounded work area, with blocks processed 256 at a time | None |
| Determinism (same input, version, parameters, OS and CPU architecture) | Yes | The variant path tested for repeatability; no randomness, no threads | Per-architecture pixel differences by design, as for v0 |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none beyond ADR-014.

Steps outside coding work: FQM decision on ADR-014.

## 4. Forensic impact

Output pixels changed: no with the defaults (goldens exact); yes when `local_frequency` is on, by explicit choice, recorded and labelled unvalidated.

Defaults or recorded parameters changed: none; `options.local_frequency` and `measurements.local_period_px` are new recorded fields.

Revalidation decision required / recorded: required before casework use (ADR-014); not recorded.

Examiner-facing wording changed (checked against forbidden claims): "Local ridge frequency", "local frequency (spacing a to b px, median m)", "local spacing a to b px (median m)"; no identification claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/frequency.py` (new) | Block spacing measurement, neighbour fill, grid spread, the six-bank interpolated filter |
| `src/ridge/pipeline/enhance.py` (new), `src/ridge/pipeline/extract.py`, `src/ridge/pipeline/__init__.py` | Enhancement step moved out; the local path; `local_period_px` on the result |
| `src/ridge/pipeline/quality.py` | `periodicity` and `ridge_quality` accept a per-pixel spacing and bank power |
| `src/ridge/pipeline/options.py` | `local_frequency` |
| `src/ridge/case/jobs.py`, `src/ridge/case/report_lines.py`, `src/ridge/case/cli_extract.py` | Measurement, "Variants" line, `--local-frequency` |
| `gui/src/ipc/types.ts`, `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/MethodVariants.tsx` (new), `gui/src/components/Check.tsx` (new), `gui/src/screens/JobSummary.tsx` | Option, fieldset split, summary |
| `gui/src-tauri/src/commands/jobs.rs`, `gui/src-tauri/src/commands/case.rs` | `local_frequency` in the request and tests; formatting |
| `tests/test_local_frequency.py` (new), `tests/test_method_options.py`, `tests/test_case_store.py`, `gui/src/test/params.test.ts` | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md` | Requirements, design, changelog, usage, guide |
| `Instruction_documentation/Handoff/Handoff_45.md` (new) | This handoff |

## 6. Data store, records and formats

Report fields added: `parameters.options.local_frequency`, `measurements.local_period_px` (object with `min`, `median`, `max`, or null). No migration.

## 7. Configuration, keys and CI

None.

## 8. Security

One more boolean through the validated option object at every boundary; the map is computed on the bounded work area. No new trust boundary, no I/O.

## 9. Tests

Tests added or updated:

- `tests/test_local_frequency.py` (new): the spacing map follows two spacings in a split image (within 8 %), stays at the nominal on an even wave, a tiny image and an empty mask; untrusted blocks (a noisy patch) and the unmeasured margin are filled from their neighbours, and far from the finger the map is nominal; the interpolated bank passes most of a unit wave at 0.75, 1.0, 1.3 and 1.6 of the nominal spacing and is deterministic; periodicity at the local spacing exceeds periodicity at the nominal on a finer wave; on a synthetic finger whose spacing runs from 7.8 to 14.2 px the default result is unchanged (no range recorded), the variant records a range whose maximum exceeds 1.3 times its minimum and brackets the global estimate, rates the coarse end at least 10 % higher in ridge quality, leaves the fine end within 5 %, keeps the print and is repeatable; on an evenly spaced arch the median agrees with the global estimate within 10 % with a narrow range; jobs record the range, the report names it, the sidecar accepts `options.local_frequency`.
- `tests/test_method_options.py`, `tests/test_case_store.py`: the options JSON includes `local_frequency`; `gui/src/test/params.test.ts`: the option is sent. Rust tests: the field maps through.

Measured on the synthetic chirp (7 to 15 px), for the record: the coarse third's mean ridge quality rose from 77 to 95 (of 255) and the fine third from 100 to 103; the recorded range was 8.0 to 13.0 px around a global estimate of 8.5 px; extraction took roughly two to three times as long as the default.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 194 source files
.venv/Scripts/python.exe -m pytest tests/test_local_frequency.py tests/test_method_options.py tests/test_case_store.py tests/test_characterization.py tests/test_upright.py -q   # 69 passed in 234 s
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 33 files, 122 tests passed (after the form split)
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass, 36 tests
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_43's branch (afis-method-channel-27, f45abb5) in a worktree: python tools/gate.py test   # all 1 gate(s) passed: test
```

Determinism and golden results: `tests/test_characterization.py` passed after the refactor (goldens exact, live v0 identical); the local path tested for repeatability.

Tests not run and why: the full `gate.py all` (stack top); this branch's and Handoff_44's full `test` gates (worktree, in turn); the GUI gate's `npm ci`/build steps; Tauri WebDriver E2E (profile exception); Apple-silicon pixel tests of the variant path (on demand).

Required tests still missing: a benchmark of the variant (validation study).

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none (the variant is off). Rollback: revert the commit.

## 11. Open risks and known issues

- The block measure inherits the global estimate's bias toward finer spacing (1/f² whitening): on an evenly spaced synthetic arch of 9 px both estimates read about 8 px. The bank is interpolated continuously, so a few per cent of bias costs little, but a benchmark should check the recorded ranges against a ruler.
- On this clean synthetic the default already keeps the whole finger; the variant raises the ridge quality where the spacing differs from the global estimate rather than the kept area. Its effect on photographs is what the benchmark must measure.

## 12. Recommended next work

Item 11 of the assessment: opt-in rectification of the finger's curvature and perspective (ADR-014 variant, FR-47).

## 13. First thing the next agent/developer should read or do

`docs/adr/ADR-014-opt-in-method-variants.md`, `src/ridge/pipeline/frequency.py`, this branch's `git show --stat`.
