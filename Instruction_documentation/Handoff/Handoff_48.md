# Handoff_48.md

Date/time (ISO 8601 with offset): 2026-10-24T18:30+02:00
Author/agent: Claude Code (claude-fable-5-1), closing handoff of the autonomous window of 2026-10-24 (Handoff_35 section 1): the AFIS-readiness assessment, items 1 to 14
Project: Ridge
Branch: `afis-docs-31` (stack top; local commits only, nothing pushed, no pull request opened)
Base commit: `dc66a41` (`main`)
Latest commit: see `git log afis-docs-31`

## 1. Scope

Requested change: "implement all of them one by one" (the fourteen items of the AFIS-readiness assessment given in this window), adhering to the coding standards and refactoring as needed; for external scale objects, a notice when none is present telling the investigator to add a ruler or an ID-1 card if possible, and otherwise to proceed.

Completed work, as a stack of branches on `main` (`dc66a41`), one item per branch, each with its own handoff:

| # | Item | Branch | Commit | Handoff |
| --- | --- | --- | --- | --- |
| 1 | Grayscale contact-like export beside the binary one (FR-37) | `afis-gray-export-19` | `d799929` | 35 |
| – | Development toolchain advisories closed in both locks | `afis-deps-20` | `fb5261d` | 36 |
| 2 | ID-1 card as a scale reference; notice when no reference was given, proceeding with the estimate (FR-31, FR-51) | `afis-scale-reference-21` | `640ff04`, `9638b0a` | 37 |
| 3 | TIFF/BMP export conversion; note when an export was enlarged to reach its resolution (FR-32) | `afis-export-formats-22` | `4191f41` | 38 |
| 4 | Submission record and AFIS cover sheet (FR-38) | `afis-submission-23` | `f98ad18` | 39 |
| 5 | Scale sweep export (FR-39) | `afis-sweep-24` | `89959e0` | 40 |
| 6 | Provenance hints for every imported photo (FR-42) | `afis-provenance-25` | `02e8257` | 41 |
| 7 | Rank-k hit rates and the CMC curve in `ridge-validate` (FR-43) | `afis-rank-metrics-26` | `96b860e` | 42 |
| 8 | Opt-in colour plane choice and specular mask (ADR-014, FR-44) | `afis-method-channel-27` | `f45abb5` | 43 |
| 9 | Opt-in upright rotation (ADR-014, FR-45) | `afis-method-upright-28` | `3fbbf94` | 44 |
| 10 | Opt-in local ridge frequency with a multi-frequency Gabor bank (ADR-014, FR-46) | `afis-method-frequency-29` | `91ea2e0` | 45 |
| 11 | Opt-in rectification of the pad's curvature (ADR-014, FR-47) | `afis-method-rectify-30` | `0fca537` | 46 |
| 12–14 | AFIS questionnaire (OQ-4), pilot protocol template, capture guidance | `afis-docs-31` | `2a65145` | 47 |

Each branch is stacked on the one above it; `afis-docs-31` holds all fourteen commits above `main`.

Out of scope, by design: the method variants are off by default and labelled unvalidated (ADR-014, proposed); no golden changed; no real data was requested, opened or processed; nothing was pushed, released or opened as a pull request.

## 2. Current repository state

Git status summary: clean on `afis-docs-31` after this handoff's commit; thirteen local `afis-*` branches above `main`. The scratchpad worktree used for the long gates was removed at the end of the window.

Recent commits: section 1.

## 3. Standards applicability and evidence

Project standards profile updated: Handoff_43 added the ADR-014 exception row (method variants off by default, recorded, pending FQM decision); no other change.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| Forensic standard §13 (method change needs an ADR, goldens, revalidation) | Yes | All pixel-affecting changes are opt-in variants under ADR-014; goldens exact at every step (`tests/test_characterization.py` in every item's test run and in the gates) | ADR-014 (proposed) |
| Forensic standard (no claims of identification, matching, validation, certification) | Yes | Wording checked in each handoff section 4; the pilot and capture documents carry non-claim statements | None |
| Biometric data rules (synthetic only, no images committed) | Yes | All tests use `tests/synthetic.py` generators; `.gitignore` untouched | None |
| Coding standards (files ≈300 lines, entrypoints 20–30 lines, parameter objects, validation at boundaries) | Yes | Splits in items 10 and 11 (`enhance.py`, `MethodVariants.tsx`, `_canvas`); every new option validated in `MethodOptions`, the sidecar and the Rust request | None |
| Determinism per architecture (ADR-009) | Yes | Repeatability tested on every variant path; per-architecture goldens untouched | Apple-silicon pixel tests not run in this window (on demand) |
| Dependency and supply-chain gates | Yes | `deps`, `secrets`, `licenses`, `sbom` gates in the final run (section 9); the dev lock advisories closed in item "deps" | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: ADR-014 awaits the FQM's decision; the Apple-silicon run and the Tauri WebDriver E2E (profile exception) were not run.

Steps outside coding work: FQM decision on ADR-014; the Product Owner sends the questionnaire (OQ-4); the DPO and the FQM take the pilot's data decision (OQ-6); the FQM approves the capture guidance.

## 4. Forensic impact

Output pixels changed: no with default options (goldens exact throughout); yes only when an examiner turns on an ADR-014 variant, which every report records and labels unvalidated.

Defaults or recorded parameters changed: no default changed. New recorded fields: `export.grayscale`, `scale.reference`, `scale.notice`, `export.resolution_note`, `submission`, `input.provenance`, `parameters.options` (channel, specular_mask, upright, local_frequency, rectify), `measurements.channel_used`, `specular_fraction`, `upright_rotation_deg`, `local_period_px`, `rectification`, `print_area.frame_px`/`rotation_deg`, custody entries `cover.export` and `sweep.export`, export index columns `format` and `written_sha256`.

Revalidation decision required / recorded: required before any variant is used in casework (ADR-014); not recorded. The default pipeline is unchanged and needs none.

Examiner-facing wording changed (checked against forbidden claims): listed per handoff; the scale notice says "No scale reference was given ... photograph the finger again with a ruler or an ISO/IEC 7810 ID-1 card ... Otherwise proceed with this estimate".

Data classes touched: synthetic only.

## 5. Files changed

Per item in Handoff_35 to Handoff_47, section 5. The stack adds, in all, the modules `pipeline/render.py`, `export/formats.py`, `case/export_file.py`, `case/submission.py`, `case/cover_sheet.py`, `export/sweep.py`, `case/sweep.py`, `case/cli_sweep.py`, `metadata/provenance.py`, `pipeline/options.py`, `pipeline/channel.py`, `pipeline/upright.py`, `pipeline/frequency.py`, `pipeline/enhance.py`, `pipeline/rectify.py`, the GUI `MethodVariants.tsx` and `components/Check.tsx`, `docs/adr/ADR-014-opt-in-method-variants.md`, the three documents of item 12, and tests for each.

## 6. Data store, records and formats

Report and custody fields added as in section 4; no schema version bump and no migration (all additions are optional fields that older readers ignore and that render as "not recorded" where a report predates them).

## 7. Configuration, keys and CI

No workflow, secret or key change. `requirements-dev.lock` and `gui/package-lock.json` updated for advisories (Handoff_36); `requirements-build.lock` left at setuptools 84.0.0 (noted there).

## 8. Security

Every new input (card points, reference kind, finger position, source agency, sweep steps, export format, option flags) is validated at the CLI, the sidecar and the Rust command; conversions and warps are bounded (`MAX_ROTATED_PIXELS`, `MAX_RECTIFIED_PIXELS`, sweep step limits); exported files are hashed and logged. No new trust boundary; the GUI WebView still holds no security logic.

## 9. Tests

Tests added or updated: per handoff. In all, the stack's full Python test gate runs about 970 tests (see below) and the GUI's vitest suite 122 tests in 33 files; the Rust crate has 36 tests.

Commands run on the stack top (`2a65145`):

```bash
# in a detached worktree of 2a65145, PYTHONPATH=<worktree>/src
.venv/Scripts/python.exe tools/gate.py docs lint format typecheck test sast deps secrets licenses sbom   # all 10 gate(s) passed; test: 976 passed, 3 skipped in 987 s; deps: no known vulnerabilities in either lock
# in the main tree at 2a65145
.venv/Scripts/python.exe tools/gate.py gui   # all 1 gate(s) passed: gui (npm lint, typecheck, prettier, vitest 122 tests in 33 files; cargo fmt, clippy, 36 tests; npm licences; cargo SBOM)
```

Earlier full `test` gates in the worktree: `4191f41` (914 passed), `f98ad18`, `96b860e`, `f45abb5` and `91ea2e0` (970 passed, 3 skipped in 1143 s) all passed; `3fbbf94` and `0fca537` were covered by the stack-top run above.

Determinism and golden results: exact at every commit (`tests/test_characterization.py`).

Tests not run and why: Apple-silicon pixel tests (no arm64 machine in this window; on demand per NFR-5); Tauri WebDriver E2E (profile exception); the GitHub Actions matrix (local gates first, per the owner's decision to minimise Actions usage).

Required tests still missing: benchmarks of the ADR-014 variants (a validation study, after OQ-4 and OQ-6).

## 10. Release readiness

Release type: internal build after merge. Ready: the stack is gated as above; merging is the owner's decision, and each branch's pull request would run the PR workflow. Blockers: none for the default pipeline; the variants stay off until ADR-014 is decided. Rollback: each item is one commit (two for item 2) and reverts cleanly in reverse stack order.

## 11. Open risks and known issues

- ADR-014 is proposed, not accepted: the five variants exist and are recorded but must not be used in casework before the FQM's decision and a validation.
- The clean synthetic fingers used in tests overstate how little the default pipeline loses; the variants' value on photographs is unknown until the pilot (Handoff_45 and Handoff_46, section 11).
- A rectified print's scale holds on the centre line only; any submission at a nominal resolution must carry the "Variants" line (Handoff_46).
- The global ridge-spacing estimate and the local map both read a few per cent fine on even synthetic prints (1/f² whitening); harmless for filtering, worth a check against a ruler in the pilot.
- Thirteen stacked branches: merging out of order or rebasing one without the others breaks the stack; the project's stacked-PR workflow (merge bottom-up, each on green CI) applies.

## 12. Recommended next work

1. Decide whether to push the thirteen branches and open their pull requests bottom-up (nothing has been pushed).
2. FQM: decide ADR-014 (accept as opt-in-only, or reject and remove the variants).
3. Product Owner: send `docs/afis_integration_questionnaire.md`; with the answers, decide FR-41 (exchange format) and the pilot (`docs/pilot_protocol.md`).
4. Run the Apple-silicon pixel tests on the stack top before any release.

## 13. First thing the next agent/developer should read or do

This handoff's section 1 table, then `git log --oneline main..afis-docs-31`; for any item, its handoff and `git show --stat <commit>`.
