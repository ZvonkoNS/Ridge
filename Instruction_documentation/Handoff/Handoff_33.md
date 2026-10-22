# Handoff_33.md

Date/time (ISO 8601 with offset): 2026-10-23T02:00+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous window granted by the product owner on 2026-10-22 ("do a refactoring run based on the instructions provided in the instructions folder")
Project: Ridge
Branch: `m5-refactor-17`, stacked on `m5-terminal-16` (Handoff_32)
Base commit: tip of `m5-terminal-16`
Latest commit: see the pull request

## 1. Scope

Requested change: a refactoring run against the limits in `Instruction_documentation/coding_standards.md` and `architecture_and_modularity_standards.md`: files about 300 lines (over 400 needs a reason), functions about 50 lines, entrypoints (CLI handlers, JSON-RPC handlers, Tauri commands) about 20 to 30 lines, refactors separate from behaviour changes, golden results identical.

How the targets were found: an AST survey of every function in `src/` (line counts below include the signature and docstring), a brace-matching survey of the Rust production code (tests excluded) and line counts of the GUI sources. Ruff already enforces complexity (C90, at most 10) and PLR limits, so those were clean before.

Completed work (four commits, structure only):

| Before | After | Commit |
| --- | --- | --- |
| `ridge.pipeline.extract.extract_fingerprint`: 114 lines | 51 lines over `_work_area`, `_rescale`, `_enhance`, `_output_window`, `_binarize`, `_debug_images` (11 to 18 lines each). Same NumPy/OpenCV calls in the same order. The debug outline's `cv2.resize` now names `INTER_LINEAR`, the default it already used (coding standard: "Every OpenCV call states interpolation") | `Split extract_fingerprint into stage helpers` |
| `ridge.case.jobs._execute`: 79 lines | 56 lines, most of it the report literal; `_store_outputs` and `_sign_and_close` keep the order of stored artefacts and custody entries (`report.sign`, `job.end`, signed head) | `Split long case functions` |
| `ridge.case.cli_extract.cmd_extract` (entrypoint): 42 lines | 15 lines; `_job_params` (same checks, same order after unlocking the identity) and `_run_job` | same |
| `ridge.case.report_html.render_report_html`: 63 lines | 38 lines; `_summary_rows`, `_input_rows`, `_result_rows`; identical HTML | same |
| `gui/src-tauri/src/sidecar.rs`: 343 production lines (692 with tests) | 175 production lines (525 with tests); new `sidecar_process.rs` (181 lines) holds the child process: spawn with the scrubbed environment, bounded line reads, shutdown, `launch`, `locate`. `sidecar.rs` re-exports what `lib.rs` and `state.rs` use, so no caller changed | `Split the sidecar process module and the prompt dispatch` |
| `prompt_calls::perform`: 150 lines | 64-line dispatch (as rustfmt lays it out) over `with_store`, `key_card`, `create_case`, `recovery_export`, `recovery_open`, `recovery_import`; same methods, parameters, timeouts and the same check that the recovery passphrase differs | same |
| `commands/jobs.rs JobRequest::params`: 57 lines | 45 lines; `checked_ruler` and `checked_roi` with the same limits and messages, in the same order | same |
| `gui/src/components/ImageViewer.tsx`: 364 lines, one 275-line component | 306 lines; `ViewerOverlay.tsx` (print area, region, ruler, minutiae marks) and `ViewerZoomBar.tsx` (zoom buttons and readout); same markup, classes, labels and characters | `Split the image viewer's overlay and zoom bar` |

Reviewed and kept, with reasons:

- `src/ridge/case/store.py` (318 lines): about 300; `OpenCase` is the case store's single write path (critical risk class), and splitting it brings no benefit worth that risk.
- `ridge.pipeline.period.estimate_period` (55 lines), `ridge.case.verify.verify_case` (49), `ridge.case.reproduce.reproduce_job` (48): about 50.
- `prompt.rs describe` (70 lines): one arm of text per prompt purpose, a data table.
- `lib.rs run` (85 lines): the Tauri builder and the `generate_handler!` list of commands.
- `gui/src/ipc/types.ts` (492 lines): IPC type declarations mirroring the sidecar schema in one place; `gui/src/dev/preview.ts` (462): development-only preview data, not in the production bundle.
- `prompt.rs` (308 production lines) and `commands/jobs.rs` (271 production lines, 321 with tests): about 300.

Out of scope: any behaviour change; the documents' content (only this handoff).

## 2. Current repository state

Git status summary: committed on `m5-refactor-17`.

## 3. Standards applicability and evidence

Project standards profile updated: not needed (no exception, no new dependency or standard).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Refactors separate from behaviour changes; golden results identical (coding standard, Git and review rules; architecture standard, Refactoring rules) | Yes | Structure-only commits. `tests/test_characterization.py` (live v0 bit-identical, stored x86-64 goldens exact) passes after the pipeline commit; the full `test` gate (section 9) | None |
| File, function and entrypoint limits | Yes | Section 1 tables | None |
| Rust: `forbid(unsafe_code)`, Clippy `-D warnings` | Yes | `cargo clippy --locked --all-targets -- -D warnings`, `cargo fmt --check`, `cargo test` (section 9) | None |
| TypeScript strict, ESLint, Prettier | Yes | `npm run typecheck`, `npm run lint`, Prettier unchanged, Vitest (section 9) | None |

## 4. Forensic impact

Output pixels changed: no (golden characterization and determinism tests pass). Defaults, recorded parameters, report content and examiner-facing wording: unchanged.

Data classes touched: synthetic test data only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/pipeline/extract.py` | Stage helpers |
| `src/ridge/case/jobs.py`, `cli_extract.py`, `report_html.py` | Shorter functions and entrypoint |
| `gui/src-tauri/src/sidecar.rs`, `sidecar_process.rs` (new), `lib.rs` | Process module split |
| `gui/src-tauri/src/prompt_calls.rs`, `commands/jobs.rs` | Helpers per purpose; checked ruler and region |
| `gui/src/components/ImageViewer.tsx`, `ViewerOverlay.tsx` (new), `ViewerZoomBar.tsx` (new) | Component split |
| `Instruction_documentation/Handoff/Handoff_33.md` (new) | This handoff |

## 6. Data store, records and formats

None.

## 7. Configuration, keys and CI

None. The pull request touches `src/ridge/pipeline/**`, so the Apple silicon pixel tests (`arm64.yml`) run on it.

## 8. Security

No change to validation, limits, the sidecar's environment scrubbing, the binary's location rules or the prompt's checks; the code moved as is.

## 9. Tests

GATE_RESULTS

## 10. Release readiness

Internal engineering build. Rollback: revert any of the four commits independently.

## 11. Open risks and known issues

- Structure-only changes in the Rust prompt and sidecar code are covered by the Rust unit tests and the live Rust-to-sidecar test, not by an end-to-end GUI test (Tauri WebDriver E2E is a recorded profile exception).

## 12. Recommended next work

1. Keep using the survey (function bodies over 50 lines, entrypoints over 30, files over 300) before each feature; add it to `tools/gate.py` as an informational report if the owner wants it enforced.

## 13. First thing the next agent/developer should read or do

Read Handoff_31 to Handoff_33 in order; they are one stack.
