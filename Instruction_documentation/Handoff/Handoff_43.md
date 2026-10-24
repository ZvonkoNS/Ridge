# Handoff_43.md

Date/time (ISO 8601 with offset): 2026-10-24T13:00+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 8 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-method-channel-27` (stacked on `afis-rank-metrics-26`; local commit only, nothing pushed)
Base commit: `96b860e` (tip of `afis-rank-metrics-26`)
Latest commit: see `git log afis-method-channel-27`

## 1. Scope

Requested change: item 8 of the assessment: an opt-in specular-highlight mask and a measured choice of the colour plane, as the first of four method variants; the owner asked for them to be implemented, and the project rules require method changes to stay off by default until validated.

Completed work:

- **ADR-014 (proposed): opt-in method variants.** `ridge.pipeline.options.MethodOptions` carries the variants; with the defaults the pipeline runs the characterised code path bit-identically (the goldens and the live-v0 comparison are unchanged and still guard it). Every job report records `parameters.options` and, under `measurements`, what the variants did; `ridge-case reproduce` rebuilds them and older reports reproduce with the defaults. The CLI, the sidecar and the Rust core validate the options; the GUI groups them under "Method variants (unvalidated, off by default)"; the readable reports carry a "Variants" line labelled unvalidated. `docs/adr/ADR-014-opt-in-method-variants.md` records the decision for the Forensic Quality Manager; the standards profile gains the exception row.
- **Colour plane (PRD FR-44, `ridge.pipeline.channel`).** `channel` chooses green (default), red, blue or luminance, or `auto`, which picks the plane whose trusted patch spectra show the sharpest ridge peak (`ridge_signal_strength`, factored out of the period estimator without changing its arithmetic); ties keep the earlier plane, so `auto` falls back to green. The plane used is recorded (`measurements.channel_used`).
- **Specular mask (FR-44, `ridge.pipeline.mask.without_specular`).** `specular_mask` removes pixels at or above 250 in any channel, grown by half a ridge spacing, from the finger area before the ridge spacing is measured again, the contrast is normalised and the region selected; the share of the finger removed is recorded (`measurements.specular_fraction`). A finger covered entirely by highlights is refused with a message.
- CLI `--channel`, `--specular-mask`; sidecar `job.run` `options`; GUI form group; Rust request validation.
- Docs: PRD §8.7 (new) with FR-44; architecture module list and ADR-014 row; the ADR file; profile exception; CHANGELOG; README; examiner guide.

Out of scope: making any variant a default (FQM decision after the benchmark, a new ADR); items 9 to 14.

## 2. Current repository state

Git status summary: committed on `afis-method-channel-27`.

Recent commits: `96b860e` (Handoff_42) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: yes (exception row for ADR-014 variants).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic standard §6 (method constants) and §13 (method change needs an ADR, goldens, revalidation) | Yes | ADR-014; constants named in one module each (`SPECULAR_LEVEL`, `AUTO_ORDER`); default-identity test and unchanged goldens | Recorded exception: variants are unvalidated and off by default |
| ADR-009 (per-architecture reproducibility) | Yes | Variants use the same OpenCV and NumPy operations as the baseline; the `auto` choice is deterministic (tested twice) | None |
| Coding standards (parameter object beyond six parameters, validation at every boundary) | Yes | `MethodOptions` frozen dataclass; `from_json` refuses unknown keys and wrong types; Rust `deny_unknown_fields` with a channel allow-list | None |
| Forbidden claims | Yes | "unvalidated" wording in the CLI line, the reports and the GUI; the ADR says variants change how the image is computed, not what it means | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: the ADR-014 exception (profile §8).

Steps outside coding work: FQM decision on ADR-014 (accept the opt-in approach; later decide defaults from the benchmark).

## 4. Forensic impact

Output pixels changed: **no with the defaults** (goldens exact, live-v0 comparison passed); **yes when a variant is on**, by the examiner's explicit choice, recorded in the report and labelled unvalidated.

Defaults or recorded parameters changed: no default changed; reports gain `parameters.options`, `measurements.channel_used`, `measurements.specular_fraction`.

Revalidation decision required / recorded: required before any variant is used in casework or made a default (ADR-014, proposed; not recorded).

Examiner-facing wording changed (checked against forbidden claims): the "Variants" line and GUI group, with "unvalidated" and the ADR reference; no identification or validation claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/options.py` (new), `src/ridge/pipeline/channel.py` (new) | Options object; colour plane choice |
| `src/ridge/pipeline/period.py` | `_trusted_patches` factored out; `ridge_signal_strength` (period arithmetic unchanged) |
| `src/ridge/pipeline/mask.py` | `without_specular` |
| `src/ridge/pipeline/extract.py`, `src/ridge/pipeline/__init__.py` | `options` argument; result fields; exports |
| `src/ridge/case/jobs.py`, `src/ridge/case/reproduce.py` | `JobParams.options`; measurements; reproduction |
| `src/ridge/sidecar/job_methods.py`, `src/ridge/sidecar/handlers.py` | `job.run` `options` |
| `src/ridge/case/cli_extract.py`, `src/ridge/case/report_lines.py`, `src/ridge/case/reports.py`, `src/ridge/case/report_html.py` | CLI flags and summary line; "Variants" line and row |
| `gui/src/ipc/types.ts`, `gui/src/screens/ParametersForm.tsx`, `gui/src/screens/JobSummary.tsx` | Form group, request field, summary |
| `gui/src-tauri/src/commands/jobs.rs` | `options` in the request, channel allow-list; tests |
| `tests/test_method_options.py` (new), `tests/test_case_store.py`, `gui/src/test/params.test.ts` | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `docs/adr/ADR-014-opt-in-method-variants.md` (new), `Instruction_documentation/Project_Standards_Profile.md`, `CHANGELOG.md`, `README.md`, `docs/examiner_guide.md` | Requirements, design, ADR, profile, changelog, usage, guide |
| `Instruction_documentation/Handoff/Handoff_43.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): report parameters gain `options`; measurements gain `channel_used` and `specular_fraction`; the custody log's `job.start` parameters carry `options`.

Migrations and recovery notes: none.

Run-record or export format changes: none.

Write paths added or changed: none.

## 7. Configuration, keys and CI

None.

## 8. Security

Decoder, limit or allow-list changes: a channel allow-list (five names) in Python and Rust; options parsed strictly (unknown keys refused).

Trust-boundary changes: `job.run` gains one object parameter, validated in Rust and in the sidecar.

Threat-model notes: none new.

Open security risks: none.

## 9. Tests

Tests added or updated:

- `tests/test_method_options.py` (new): options validation and JSON round trip; default options give results bit-identical to the plain call (image, grayscale twin, period); `auto` picks the blue plane on a photo whose ridges survive only there, deterministically, equals the explicit `blue` choice, while the default plane fails to extract; the specular mask removes a painted highlight (positive fraction, every highlight pixel out, grown by half a spacing), refuses an all-white finger, and reports 0.0 on a clean photo; jobs record and reproduce the options, older reports reproduce with defaults, the text report's "Variants" line appears only when a variant is on; CLI flags and the argparse refusal; sidecar `job.run` with valid, unknown-plane and unknown-key options.
- `tests/test_case_store.py`: the full parameter assertion includes `options`; `tests/test_characterization.py` (unchanged) passes: goldens and live v0 identical.
- `gui/src/test/params.test.ts`: options sent explicitly and when turned on. Rust tests: options map through; an unknown plane is refused.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 189 source files
.venv/Scripts/python.exe -m pytest tests/test_method_options.py tests/test_pipeline_units.py tests/test_characterization.py tests/test_case_store.py tests/test_case_reproduce.py tests/test_sidecar.py tests/test_case_reports.py -q   # pass
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 33 files, 122 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Earlier branches in a worktree: afis-submission-23 (f98ad18) python tools/gate.py test -> all 1 gate(s) passed; afis-rank-metrics-26 (96b860e) running
```

Determinism and golden results: `tests/test_characterization.py` passed (stored goldens exact on this workstation; live v0 identical); `auto` tested for repeatability.

Tests not run and why: the full `gate.py all` (stack top); this branch's full `test` gate (worktree, in turn); the GUI gate's `npm ci`/build steps; Tauri WebDriver E2E (profile exception); Apple-silicon pixel tests for the new variant paths (on-demand workflow; the defaults are unchanged).

Required tests still missing: a benchmark of the variants on the consented set (the validation study, not a CI test).

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch (the variants are off). Rollback: revert the commit; reports with `options` still verify (unknown keys are ignored by older renderers).

## 11. Open risks and known issues

- A variant used before validation would produce an export whose provenance differs from the validated method; the report says so, but the limits of use do not yet refuse variants (the FQM can add a rule if wanted).

## 12. Recommended next work

Item 9 of the assessment: opt-in rotation to upright (ADR-014 variant).

## 13. First thing the next agent/developer should read or do

`docs/adr/ADR-014-opt-in-method-variants.md`, then Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
