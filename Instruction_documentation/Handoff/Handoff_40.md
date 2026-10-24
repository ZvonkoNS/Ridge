# Handoff_40.md

Date/time (ISO 8601 with offset): 2026-10-24T12:15+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 5 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-sweep-24` (stacked on `afis-submission-23`; local commit only, nothing pushed)
Base commit: `f98ad18` (tip of `afis-submission-23`)
Latest commit: see `git log afis-sweep-24`

## 1. Scope

Requested change: item 5 of the assessment: a scale sweep export for exports whose scale is only estimated.

Completed work:

- **Scale sweep (PRD FR-39).** `ridge-case sweep CASE SHA --to FOLDER [--steps 3|5|7|9] [--format png|tiff|bmp]`, the GUI's "Export scale sweep..." (shown in the review panel for a comparison export whose scale uncertainty is above zero) and sidecar `sweep.export` take one comparison export (`export` or `export-gray`), read its declared resolution and scale uncertainty from the job's verified report, and write rescaled copies at factors spread evenly from 1 − u to 1 + u (default three: for ±15 %, 0.85, 1.00 and 1.15), resampled like the 500 ppi scaling and each declared at the export's resolution, so an AFIS reads them as images of different physical size to be searched separately. Each file is hashed and logged as `sweep.export` (`sha256`, `source_sha256`, `role`, `job_id`, `factor`, `ppi`, `destination`); `SWEEP.csv` indexes the folder with file, factor, hash, size, declared ppi, source, job, scale method and uncertainty. An exact scale, an uncertainty above 50 %, a non-export item, an even or out-of-range step count or an existing folder is refused; a sweep that stops part-way keeps and indexes the files already written. New modules `src/ridge/export/sweep.py` (pure) and `src/ridge/case/sweep.py` (the logged writes), CLI module `src/ridge/case/cli_sweep.py`, Rust command `export_sweep`.
- Docs: PRD FR-39; architecture §7.3 row and §8.3 paragraph; CHANGELOG; README; examiner guide.

Out of scope: choosing the factors for a given AFIS (the operator's practice); items 6 to 14.

## 2. Current repository state

Git status summary: committed on `afis-sweep-24`.

Recent commits: `f98ad18` (Handoff_39), `4191f41` (Handoff_38) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic standard §7 (scale is an assumption without a reference) | Yes | The sweep spans the recorded uncertainty only; every file names its factor and source; nothing is matched or ranked | None |
| FR-22/FR-25 single logged export path | Yes | Every file goes through `publish_logged`; one `sweep.export` entry per file | None |
| Coding standards (validation, bounds, ≤ ~300 lines) | Yes | Factors and steps validated; `MAX_EXPORT_PIXELS` bound on every rescale; new modules 60, 160 and 45 lines | None |
| Forbidden claims | Yes | The CLI says the files are rescaled copies, not new evidence; the GUI says they are for searches at several scales | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the AFIS team decides whether multi-scale searches of photographed prints are its practice and how many steps it wants (OQ-4).

## 4. Forensic impact

Output pixels changed: no stored output changed; the sweep writes derived copies outside the store, each recorded with its factor and source.

Defaults or recorded parameters changed: none. New custody action `sweep.export`.

Revalidation decision required / recorded: not required (no method change); whether sweeps help an AFIS search is for the pilot (assessment item 12).

Examiner-facing wording changed (checked against forbidden claims): the sweep button, its title, the CLI lines and the guide bullet; no identification or matching claim.

Data classes touched: synthetic only.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/export/sweep.py` (new) | `sweep_factors`, `rescaled` |
| `src/ridge/case/sweep.py` (new) | `export_sweep`, the index, logged writes |
| `src/ridge/case/cli_sweep.py` (new), `src/ridge/case/cli.py` | `ridge-case sweep` |
| `src/ridge/sidecar/job_methods.py`, `src/ridge/sidecar/handlers.py` | `sweep.export` |
| `gui/src/ipc/types.ts`, `gui/src/ipc/commands.ts`, `gui/src/screens/ReviewPanel.tsx`, `gui/src/dev/preview.ts` | The sweep button and result message |
| `gui/src-tauri/src/commands/case.rs`, `gui/src-tauri/src/commands/list.rs`, `gui/src-tauri/src/lib.rs`, `gui/src-tauri/capabilities/main.json` | `export_sweep` command, validated, registered and allowed |
| `tests/test_sweep.py` (new), `gui/src/test/sweep.test.tsx` (new) | Tests (section 9) |
| `docs/prd.md`, `docs/architecture.md`, `docs/examiner_guide.md`, `CHANGELOG.md`, `README.md` | Requirements, design, guide, changelog, usage |
| `Instruction_documentation/Handoff/Handoff_40.md` (new) | This handoff |

## 6. Data store, records and formats

Case-store, custody-log or report format changes (M1+): new custody action `sweep.export`; no report change.

Migrations and recovery notes: none.

Run-record or export format changes: a new export folder kind with `SWEEP.csv`.

Write paths added or changed: the sweep writes into a new examiner-chosen folder through `publish_logged`, like the bulk export.

## 7. Configuration, keys and CI

None.

## 8. Security

Decoder, limit or allow-list changes: the stored export is decoded by the bounded PNG reader of item 3; every rescale is bounded by `MAX_EXPORT_PIXELS`; steps and format are allow-listed in Python and Rust.

Trust-boundary changes: one new Tauri command mapping to one sidecar method; the folder comes from the native dialog.

Threat-model notes: the sweep reads the uncertainty from the verified report, so a tampered report cannot drive it; file names carry the stored label and the factor only.

Open security risks: none.

## 9. Tests

Tests added or updated:

- `tests/test_sweep.py` (new): factor spacing for 3 and 5 steps and refusals (even, out of range, zero or absurd uncertainty); rescaled sizes, identity at 1.0, determinism and the pixel bound; a sweep of the grayscale export writes three logged files declared at 500 ppi with growing sizes, the middle one byte-identical to the stored export, with a correct index; existing folder and print refused with nothing left behind; TIFF with five steps; CLI and sidecar, including an unknown format refused.
- `gui/src/test/sweep.test.tsx` (new): the button appears only for an uncertain scale, sends the item and defaults, and reports the factors.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 184 source files
.venv/Scripts/python.exe -m pytest tests/test_sweep.py tests/test_case_cli.py tests/test_sidecar.py -q   # pass (after one assertion took the canonical JSON's 15 for 15.0)
cd gui && npm run lint && npm run typecheck && npx prettier --check . && npm test -- --run   # 32 files, 119 tests passed
cd gui/src-tauri && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked   # pass
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_38's branch (afis-export-formats-22, commit 4191f41) in a worktree: python tools/gate.py test
#   -> 914 passed, 3 skipped in 926 s; coverage above 90 %: all 1 gate(s) passed
```

Determinism and golden results: no pipeline change; rescaled copies are deterministic (tested).

Tests not run and why: the full `gate.py all` (stack top); this branch's and Handoff_39's full `test` gate (run in a worktree after the commit; results in the next handoff); the GUI gate's `npm ci`/build steps; Tauri WebDriver E2E (profile exception).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit; sweep folders already written stay valid, logged copies.

## 11. Open risks and known issues

- A sweep multiplies the files an operator handles; the index and the custody log keep them traceable, but the operator's own records must note which copy produced a candidate.

## 12. Recommended next work

Item 6 of the assessment: provenance hints.

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
