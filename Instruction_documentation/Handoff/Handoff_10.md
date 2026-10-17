# Handoff_10.md

Date/time (ISO 8601 with offset): 2026-10-17T10:25+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `m5-compare-reproduce` (built on `m5-case-reports`) → PR after PRs #5, #6, #7 and #8

## 1. Scope

| Part | What |
| --- | --- |
| Reference images (PRD FR-52 back end) | `OpenCase.import_reference(path, source)` stores NAFIS/AFIS candidate images with role `reference` (folder `references/`). It records the examiner's source note and treats them like evidence: validated, hashed, encrypted, logged as `reference.import`. Jobs refuse them. `StoredItem.source` exposes the note |
| Comparison sheet (`ridge.case.compare`) | One export and one reference are decoded (both reads logged) and resampled to one resolution (default 500 ppi). Each gets a 10 mm scale bar and captions (hash, label, resolution and its origin). The sheet carries the "view aid only" disclaimer and is written as grayscale PNG with pHYs. It is logged as `comparison.export` with the export, reference and sheet hashes. The reference's resolution comes from its file or from the examiner, and must lie between 250 and 2000 ppi. A 72 or 96 ppi default is refused, never guessed. Columns are sized to their captions; captions are ASCII and truncated (the full note stays in the log) |
| Reproduction check (`ridge.case.reproduce`, FR-34, NFR-3) | Loads a verified report and rebuilds `JobParams` from it alone (reports from before M3 have no minutiae flag). It re-runs the job as a normal logged and signed job and compares every output by role, label and SHA-256: matched, differing, missing or extra. Environment changes (version, platform, machine, dependencies) are reported. The result is logged as `job.reproduce` `ok`/`mismatch` under a new signed head. Identical outputs are deduplicated |
| CLI | `ridge-case import-reference`, `ridge-case compare`, `ridge-case reproduce` (exit 1 on any difference; control characters neutralised) |
| Sidecar | `case.import_reference`, `compare.export`, `job.reproduce`; items now carry `source` |

## 2. Evidence

`tests/test_case_compare.py` covers:

- hashing and logging of references, and that jobs refuse them;
- the artefact-role guard, duplicates, and verification;
- equal scale (a 1000 ppi reference is halved at 500 ppi), pHYs and custody hashes;
- missing, default (72 ppi) and implausible resolutions;
- examiner-given resolution;
- role checks and the no-overwrite rule;
- size caps, both while resampling and while composing;
- lost export metadata, and anisotropic resolution.

`tests/test_case_reproduce.py` covers:

- a bit-identical same-platform re-run including debug and minutiae outputs, with nothing new stored and the case still verifying;
- a simulated other-platform drift (changed pixel and machine), logged as a mismatch with environment changes;
- missing outputs;
- parameter round trips, including the ruler and pre-M3 reports;
- incomplete parameters;
- unknown jobs.

The CLI and sidecar end-to-end tests cover the new commands. `compare.py` and `reproduce.py` have 100 % line and branch coverage.

**Review fixes (PR #9):**

- A re-run that fails outright is logged as `job.reproduce` `failed`, linked to the original job, under a new signed head (`test_a_failed_rerun_is_logged_and_linked`).
- One blob has one role: importing a file that is byte-identical to a stored item of another role, such as a reference identical to evidence, is refused instead of silently resolving to the other role (`test_one_blob_has_one_role`).

## 3. Forensic impact

- The comparison sheet supports the examiner's manual comparison (ACE-V). Ridge never aligns, matches or scores, and every sheet says so.
- Equal scale depends on the reference's declared or examiner-given resolution and on the export's scale method (ridge-period assumption ±15 % without a ruler, recorded in its report). The sheet does not repeat the export's uncertainty; read it from the job report.
- `reproduce` gives the lab a one-command check of FR-34 / NFR-3 on a workstation, for example after an update or on a newly validated machine. Each run adds a job to the case and is logged.

## 4. Open items

- **CI is still blocked** by the GitHub Actions billing or spending-limit problem. All branches pass the local gate. Merge order: #5 → #6 → #7 → #8 → this branch, each after its CI matrix is green.
- The GUI (FR-50 to FR-53) needs the Tauri shell. It also needs an owner decision on how the native passphrase prompt is implemented per OS: Windows Credential UI, macOS `SecurityAgent`/LocalAuthentication, or a minimal native dialog crate.
- OQ-4 (exchange format) still blocks FR-41.

## 5. First thing to do

Restore GitHub Actions, then merge the PR stack in order. Then read `src/ridge/case/compare.py` and `src/ridge/case/reproduce.py`.
