# Handoff_2.md

Date/time (ISO 8601 with offset): 2026-10-17T08:35+02:00
Author/agent: Claude Code (claude-opus-5-5), working with the repository owner
Project: Ridge
Branch: `per-arch-reproducibility` → PR [ZvonkoNS/Ridge#1](https://github.com/ZvonkoNS/Ridge/pull/1) into `main`
Base commit: `5e0bc28` (merge of M0 foundation)
Latest commit: see PR #1. This handoff ships in the PR's final commit.

## 1. Scope

Requested change:

1. Fix the first CI failure on `main`. It happened on macOS only: three golden tests on Apple silicon.
2. Add a live, bit-identical v0 check on every platform.
3. Store goldens per CPU architecture.
4. Make reproducibility and validation per CPU architecture in the PRD (NFR-3, R-7).
5. Get CI green.

Completed work:

- **Live v0 check:** `tests/test_characterization.py::test_bit_identical_to_live_v0` loads v0 from git history (`3441cf8`, via `tests/reference.py`), runs it next to the package on the same machine, and requires bit-identical images, ridge spacing, finger detection, debug images and error messages.
- **Per-architecture goldens:** `tests/golden/v0-x86_64.*` (regenerated on the reference workstation; arrays identical to the former `v0.*`) and `tests/golden/v0-arm64.*` (generated on GitHub's macOS arm64 runner by the new `golden` workflow).
- **Stored-golden comparison:** bit-identical on the reference machine. Elsewhere, same-architecture tolerances apply: ≥ 99.9% of output pixels, ridge spacing to 1e-6 relative, and debug images within a mean of 1 grey level (they are quantised float maps).
- **CI:** full-history checkout for the gates job; new `.github/workflows/golden.yml` (manual, and on PRs touching golden inputs) that uploads goldens per runner type.
- **Documents:** reproducibility and validation are now per (release, OS, CPU architecture):
  - PRD v0.3: G-3, NFR-3, NFR-5, R-7 (materialised), §12 item 7, new OQ-15;
  - architecture: QA-2, §11 numerics, §12, ADR-009;
  - standards profile, forensic standards §6, coding standards numerics, testing gates, CLAUDE.md, README.

Out of scope: M1 (case store, custody, signed reports), the owner decisions on OQ-15, and any change to the extraction algorithm.

## 2. Current repository state

Git status summary: all work is committed on `per-arch-reproducibility` and pushed; the PR is open against `main`.

Recent commits: `6021c40` (live v0 check, per-architecture goldens, CI), then this commit (arm64 goldens and documents).

## 3. Standards applicability and evidence

Project standards profile updated: yes. The "goldens only bit-identical on the reference platform" exception is replaced by "results differ between CPU architectures; validation per architecture".

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| ISO/IEC 14764 regression protection | Yes | Live v0 bit-identical check on every CI platform | — |
| IEEE 754 / numerical reproducibility (NFR-3) | Yes | Measurements in §4 | Cross-architecture results differ by design (ADR-009) |
| ISO/IEC 17025 7.2.2 method validation | Yes (M5) | PRD §12 item 7: validation per architecture | OQ-15 open |
| NIST SSDF (supply chain of test data) | Yes | arm64 goldens produced by a pinned CI workflow from v0 in git history, then checked (12 `uint8` arrays, no pickles, matching versions) | — |

Standards checks or tools run:

```bash
python tools/gate.py all            # Windows x86-64: all 10 gates passed; 116 passed, 2 skipped; coverage 97.39%
RIDGE_GOLDEN_MODE=tolerant python -m pytest tests/test_characterization.py   # 22 passed
# GitHub Actions "golden" run 39009964143: ubuntu, windows and macos all succeeded (artifacts compared in §4)
```

Exceptions, deviations or evidence gaps: casework architectures are not yet decided (OQ-15). arm64 exactness is only checked on GitHub's macOS runners, not on a lab Mac.

Steps outside coding work: the Forensic Quality Manager and IT decide which architectures casework uses (OQ-15); each one needs its own validation (M5).

## 4. Forensic impact

Output pixels changed: **no**. The package is bit-identical to v0 on every platform; this is now tested live.

**Measured reproducibility (golden cases, numpy 2.5.4, OpenCV 5.0.0, Pillow 12.3.0):**

| Comparison | Result |
| --- | --- |
| Reference workstation (Windows 11, Intel) vs GitHub Windows Server 2025 runner (x86-64) | All 8 outputs and all debug images **bit-identical** |
| Reference workstation vs GitHub Ubuntu runner (Linux x86-64) | All 8 outputs and all debug images **bit-identical** |
| x86-64 vs arm64 (GitHub macOS 26, Apple silicon) | See table below |

| Case | Ridge spacing x86-64 / arm64 (px) | Output pixels agreeing |
| --- | --- | --- |
| whorl_default | 8.8120 / 8.8120 | 99.9525% |
| whorl_flip | 8.8120 / 8.8120 | 99.8535% |
| whorl_no_crop | 8.8120 / 8.8120 | 99.9797% |
| whorl_period_override | 10.0000 / 10.0000 | 99.9054% |
| whorl_strict_quality | 8.8120 / 8.8120 | 99.9598% |
| arch_default | 9.5076 / 9.5076 | 99.9378% |
| arch_large_period | 13.7023 / 13.7742 (+0.52%) | output 291x492 vs 293x492: not comparable pixel by pixel |
| grey_whole_frame | 8.3856 / 8.3856 | 100% (identical) |
| too_low_resolution, noise_only | same errors and messages | — |

Debug images (whorl_default) between architectures: the mean absolute difference is 0.05–0.5 grey levels. Isolated pixels differ by up to 71 levels ("normalized") and 88 ("region" overlay, JPEG).

**Interpretation:** x86-64 results are stable across operating systems and CPUs tested. Apple silicon produces slightly different prints, and in one case a slightly different ridge spacing and print size. A print made on a Mac and one made on a Windows workstation from the same photo are therefore not interchangeable as evidence unless both architectures are validated (PRD NFR-3, §12).

Revalidation decision required / recorded: none for M0. OQ-15 must be answered before M5.

**Review follow-up (PR #1, automated Codex review of `6021c40`):**

- "Commit the arm64 golden files": already done in `5dcbf44`.
- "Keep enforcing the cross-architecture acceptance threshold": the threshold was changed on the product owner's instruction, not dropped. A cross-architecture envelope check was added: `tests/cross_arch.py` and `tests/test_cross_architecture.py`, with drift-rejection tests, plus `tools/compare_goldens.py` for release handoffs. The approval is recorded in PRD NFR-3 and the standards profile; Forensic Quality Manager confirmation is pending.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `tests/reference.py` | Shared v0 loader and runner, architecture key, golden paths |
| `tests/conftest.py` | Per-architecture golden fixture; live v0 fixture |
| `tests/test_characterization.py` | Live v0 bit-identical test; per-architecture golden test with grey-level tolerance for debug images |
| `tests/golden_cases.py` | Uses the shared reference constant |
| `tests/cross_arch.py`, `tests/test_cross_architecture.py`, `tools/compare_goldens.py` | Cross-architecture envelope check and report |
| `tests/golden/v0-x86_64.*`, `tests/golden/v0-arm64.*` | Per-architecture goldens (replace `v0.*`) |
| `tools/make_golden.py` | Writes `v0-<arch>.*` and records the architecture; `--out-dir` |
| `.github/workflows/ci.yml`, `.github/workflows/golden.yml` | Full history for the live v0 test; golden-generation workflow |
| `docs/prd.md`, `docs/architecture.md`, standards profile, pack documents, `CLAUDE.md`, `README.md` | Per-architecture reproducibility and validation |

## 6. Data store, records and formats

No changes.

## 7. Configuration, keys and CI

- New workflow `golden.yml`: `contents: read`, actions pinned by SHA.
- `ci.yml`: the gates job uses `fetch-depth: 0`.
- No new configuration keys or secrets.

## 8. Security

No changes to decoders, limits or trust boundaries. The downloaded CI artifacts were checked before committing: `.npz` loaded with pickles disabled, `uint8` arrays only, metadata matching the reference commit and library versions.

## 9. Tests

- Tests added or updated: 10 new live v0 tests; stored-golden tests now load per architecture.
- Commands run: see §3.
- Determinism and golden results: see §4.
- Tests not run: POSIX permission tests on Windows (skipped by design). The full gate suite runs on the PR CI matrix.
- Required tests still missing: unchanged from Handoff_1 (fuzzing, NFR-1 measurement, W1 output-folder containment).

## 10. Release readiness

Release type: internal engineering build.

Ready: no (same blockers as Handoff_1: owners, M1, DPIA, validation).

Rollback or mitigation: revert PR #1. The goldens and tests are self-contained.

## 11. Open risks and known issues

- R-7 has materialised. It is managed by per-architecture validation (OQ-15).
- If GitHub's macOS runners move to a different arm64 CPU generation, the stored arm64 goldens might drift. The tolerant comparison and the live v0 check keep CI meaningful; regenerate with the `golden` workflow if needed and record it in a handoff.

## 12. Recommended next work

1. Owner decision on OQ-15 (casework architectures).
2. M1: encrypted case store, custody log and signed reports (Security Owner input on OQ-9, OQ-12, OQ-13).
3. Fuzzing for `decode_image`; NFR-1 measurement.

## 13. First thing the next agent/developer should read or do

Run `python tools/gate.py all`. Then read PRD §7–§8.3 and ADR-009 before touching anything that can change output pixels.
