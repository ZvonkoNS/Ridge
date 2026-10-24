# Handoff_58.md

Date/time (ISO 8601 with offset): 2026-10-25T05:40+02:00
Author/agent: Claude Code (claude-fable-5-1), closing handoff: the AFIS-readiness stack and the end-user review follow-up merged into `main`; branches and worktrees cleaned
Project: Ridge
Branch: `main`
Base commit: `dc66a41` (`main` before the stack)
Latest commit: see `git log main` (the merge of #51 is `e2f6f54`; this handoff follows it)

## 1. Scope

Requested change: push everything to `main` and clean the branches and the repository, after the README, the code comments and the installers (Handoff_57).

Completed work:

- **Merged into `main`, bottom-up, each pull request retargeted to `main` after the one below it merged, merge commits kept:** #34 (`afis-deps-20`, which also carried the grayscale export of the closed #33), #35 `afis-scale-reference-21`, #36 `afis-export-formats-22`, #37 `afis-submission-23`, #38 `afis-sweep-24`, #39 `afis-provenance-25`, #40 `afis-rank-metrics-26`, #41 `afis-method-channel-27`, #42 `afis-method-upright-28`, #43 `afis-method-frequency-29`, #44 `afis-method-rectify-30`, #45 `afis-docs-31`, #46 `afis-capture-check-32`, #47 `afis-research-mode-33`, #48 `afis-annotations-34`, #49 `afis-linked-marking-35`, #50 `afis-release-check-36`, #51 `afis-review-fixes-37`. The stack was linear, so `main` now holds exactly the tree of the stack top (`9366cc2`): `git diff 9366cc2 main` is empty.
- **Before the merge:** every Codex thread on the stack was fixed, answered and resolved (eighteen on #35 to #49 in Handoff_57, one on #51); the full gate passed on the stack top (section 9); every pull request's CI was green or had no checks (documents-only or GUI-only changes, which `ci.yml` ignores).
- **Cleanup:** the eighteen merged remote branches deleted on `origin`; the nineteen local `afis-*` branches deleted; the scratchpad gate worktree removed and worktrees pruned; no open pull requests remain. The worktree `.claude/worktrees/friendly-dhawan-47db97` on `m5-missing-engine-13` belongs to another session and was left alone.
- **What `main` gained since `dc66a41`** (46 commits): the fourteen items of the AFIS-readiness assessment (Handoff_35 to Handoff_48), the four end-user review items (Handoff_50 to Handoff_54), ADR-015 and ADR-016 accepted with the release build and installer check (Handoff_56), the Codex fixes, the README manual and the Windows installers (Handoff_57), and the push and pull-request handoffs (49, 55).

Out of scope: a release tag (none made); macOS and Linux installers; the FQM's decision on ADR-014.

## 2. Current repository state

Git status summary: `main` clean and pushed; no feature branches; no open pull requests.

Recent commits: `e2f6f54` (merge of #51) and the seventeen merges below it.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| PR workflow (local gate first, Codex threads fixed and resolved, merge bottom-up on green CI) | Yes | Section 9; the merge log; every thread resolved with a reply naming the fix | The fixes for the lower pull requests landed through the top one in the same pass (Handoff_57 §11) |
| Minimal GitHub Actions use | Yes | One CI run per pull request; no re-runs requested; retargeting triggered none | None |
| Handoff discipline (next consecutive number, never overwritten) | Yes | Handoff_35 to Handoff_58 | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none new.

Steps outside coding work: the FQM decides ADR-014; the Product Owner sends the AFIS questionnaire; the DPO and the FQM take the pilot's data decision; code signing at release.

## 4. Forensic impact

Output pixels changed: no for default options, throughout the stack (goldens exact in every gate). The opt-in variants (ADR-014) change pixels only when switched on, recorded and labelled unvalidated.

Defaults or recorded parameters changed: `export-all` defaults to the grayscale export (ADR-015); the report gained several additive fields (Handoff_48 §4, Handoff_57 §6); new custody actions for annotations and their export.

Revalidation decision required / recorded: not for the default pipeline; required before any variant is used in casework.

Examiner-facing wording changed (checked against forbidden claims): per handoff; no identification, matching or validation claim anywhere.

Data classes touched: synthetic only.

## 5. Files changed

This handoff only. The stack's files are listed per handoff.

## 6. Data store, records and formats

As Handoff_48 §6 and Handoff_52 §6; no schema version bump.

## 7. Configuration, keys and CI

None.

## 8. Security

No change in this handoff.

## 9. Tests

Gates on the stack top before the merge:

```bash
# worktree of f0ccca7 (the last Python change), PYTHONPATH=<worktree>/src
.venv/Scripts/python.exe tools/gate.py docs lint format typecheck test sast deps secrets licenses sbom   # all 10 gate(s) passed
# main tree at 9366cc2 (the last commit, GUI only)
.venv/Scripts/python.exe tools/gate.py gui   # all 1 gate(s) passed: gui (vitest 141 tests, 36 Rust tests)
```

GitHub: the Linux gate, the dependency audit and, where pipeline or export paths changed, the arm64 pixel tests were green on every pull request that had checks.

Determinism and golden results: exact (`tests/test_characterization.py` in the test gate).

Tests not run and why: the full matrix on Windows, Linux and macOS runners (runs on demand or for a release tag, per the owner's decision); Tauri WebDriver E2E (profile exception); the MSI install (administrator).

Required tests still missing: the method validation study; calibration of the capture check on real photographs (pilot).

## 10. Release readiness

Release type: `main` is an internal engineering state, not a release; no tag was made. The installers under `installers/` are unsigned engineering builds of `56c15b8`, two commits behind the fixes of #51 (which change no bundled Python behaviour except the review fixes; rebuild before any release). Blockers for an operational release are unchanged (Handoff_34, Handoff_48).

## 11. Open risks and known issues

- The installers in `installers/` predate the Codex fixes of #51 by one Python change set; rebuild them (Handoff_56's procedure) before handing them to anyone.
- Two large binaries now live in the repository's history (Handoff_57 §11).
- ADR-014 remains proposed; the variants stay research-only.

## 12. Recommended next work

1. Rebuild the installers from `main` and replace the files under `installers/` (or move to release assets).
2. The pilot (Handoff_47) once OQ-4 and OQ-6 are answered; the FQM's decision on ADR-014.
3. A bundle job for macOS and Linux in `.github/workflows/gui.yml` if those installers are wanted.

## 13. First thing the next agent/developer should read or do

`README.md`, then this handoff's section 1 and `git log --oneline --merges dc66a41..main`.
