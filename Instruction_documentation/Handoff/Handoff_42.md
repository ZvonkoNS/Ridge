# Handoff_42.md

Date/time (ISO 8601 with offset): 2026-10-24T12:45+02:00
Author/agent: Claude Code (claude-fable-5-1), autonomous window of 2026-10-24 (Handoff_35 section 1), item 7 of the AFIS-readiness assessment
Project: Ridge
Branch: `afis-rank-metrics-26` (stacked on `afis-provenance-25`; local commit only, nothing pushed)
Base commit: `02e8257` (tip of `afis-provenance-25`)
Latest commit: see `git log afis-rank-metrics-26`

## 1. Scope

Requested change: item 7 of the assessment: identification-mode metrics in `ridge-validate`, because an AFIS search is a 1:N identification judged by the mate's rank, not a verification threshold.

Completed work:

- **Rank metrics (PRD FR-43, §12).** `ridge-validate --ranks ranks.csv [--rank K ...]` reads one row per 1:N search run outside Ridge (`probe`, `rank` of the mate or empty when it was not returned, optional `group` with the same rules as the score file) and reports rank-k hit rates with Wilson 95 % intervals (default k = 1, 5, 10, 20), the CMC curve up to the highest returned rank (capped at 200) and the count of mates not returned, overall and per group, under `identification` in the JSON report. The score file is now optional, so an identification-only study works; both together give both sections. New functions `hit_rate`, `cmc_curve`, `not_returned`, `HitRate` and the shared `wilson_interval` in `ridge.validation.metrics`; `read_ranks`, `summarise_identification` and the extended `build_report` in `ridge.validation.report`. Ranks are bounded (1 to 1000) and the file is validated strictly like the score file.
- Docs: PRD §12 item 2 and FR-43; README; CHANGELOG.

Out of scope: running any benchmark (needs the consented set and a matcher outside Ridge); items 8 to 14.

## 2. Current repository state

Git status summary: committed on `afis-rank-metrics-26`.

Recent commits: `02e8257` (Handoff_41) and the earlier stack below this one.

## 3. Standards applicability and evidence

Project standards profile updated: not needed.

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 19795-1 (identification metrics: rank-k identification rate, CMC) | Yes | Hand-checked tests (`tests/test_validation_metrics.py`): hit rates, monotone CMC, not-returned count, Wilson intervals as mirrors of the error-rate intervals | Intervals assume independent searches (stated in the report's `method`) |
| Coding standards (strict parsing at the trust boundary, bounded input) | Yes | Rank file read through the bounded reader; header, probe, rank range and group rules checked row by row; tests for each refusal | None |
| Forbidden claims | Yes | The report describes matcher outcomes on the validation set; no case-level conclusion | None |

Standards checks or tools run: section 9.

Exceptions, deviations or evidence gaps: none.

Steps outside coding work: the Forensic Quality Manager chooses the ranks to report in the validation plan; the AFIS pilot (assessment item 12) produces the rank file.

## 4. Forensic impact

Output pixels changed: no. Defaults or recorded parameters changed: no (a validation tool; job reports are untouched). Revalidation decision: not applicable. Examiner-facing wording changed: the tool's help and README only. Data classes touched: synthetic numbers only; the validation set never enters the repository.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `src/ridge/validation/metrics.py` | `wilson_interval`, `HitRate`, `hit_rate`, `cmc_curve`, `not_returned`, `MAX_RANK` |
| `src/ridge/validation/report.py` | `read_ranks`, `summarise_identification`, `build_report` with optional scores and ranks, CLI options |
| `tests/test_validation_metrics.py` | Tests (section 9) |
| `docs/prd.md`, `README.md`, `CHANGELOG.md` | §12, FR-43, usage, changelog |
| `Instruction_documentation/Handoff/Handoff_42.md` (new) | This handoff |

## 6. Data store, records and formats

None (the validation report schema `ridge.validation/1` gains an optional `identification` section; `overall`, `det_curve` and `groups` are now present only when scores were given).

## 7. Configuration, keys and CI

None.

## 8. Security

A second CSV input, read through the same bounded reader with strict validation; no new trust boundary.

## 9. Tests

Tests added or updated (`tests/test_validation_metrics.py`): hit rates and the CMC by hand, mirrored Wilson intervals, refusals (empty list, rank 0, k 0, k above 1000); a rank file with groups and the report's identification section (overall, per group, curve end, no verification section without scores, both inputs required); malformed rank files (non-numeric, zero, empty probe, missing header, empty or reserved group, no rows); the CLI with ranks only, with both files, with neither (usage error) and with a missing file.

Commands run:

```bash
.venv/Scripts/python.exe -m ruff check src tests tools && .venv/Scripts/python.exe -m ruff format --check src tests tools   # clean
.venv/Scripts/python.exe -m mypy                                                        # Success: no issues found in 186 source files
.venv/Scripts/python.exe -m pytest tests/test_validation_metrics.py -q                 # 34 passed
.venv/Scripts/python.exe tools/gate.py docs   # pass
# Handoff_39's branch (afis-submission-23, f98ad18) in a worktree: python tools/gate.py test (running; result in the next handoff)
```

Determinism and golden results: no pipeline change.

Tests not run and why: the full `gate.py all` (stack top); GUI and Rust checks (no GUI or Rust change on this branch).

Required tests still missing: none for this item.

## 10. Release readiness

Release type: internal build. Ready: as part of the stack. Blockers: none from this branch. Rollback: revert the commit.

## 11. Open risks and known issues

- Wilson intervals treat searches as independent; several searches of the same finger (for example a scale sweep, FR-39) are not, so the intervals are optimistic, as the report says.

## 12. Recommended next work

Item 8 of the assessment: opt-in specular-highlight mask and measured input-channel choice (method change, ADR, off by default).

## 13. First thing the next agent/developer should read or do

Handoff_35 section 12 for the order of the stack; this branch's `git show --stat`.
