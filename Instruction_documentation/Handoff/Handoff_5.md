# Handoff_5.md

Date/time (ISO 8601 with offset): 2026-10-17T09:40+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window. The export and NFIQ 2 building blocks were written by a sub-agent on branch `m2-export`, then reviewed and integrated here.
Project: Ridge
Branch: `m2-integration`. It contains M1 with its review fixes (`m1-case-store`), the hardening follow-ups (`hardening-followups`) and `m2-export`. PR into `main` follows PRs #2 and #3.

## 1. Scope

**M2 Matcher-ready output** (PRD FR-30 to FR-34):

| Part | What |
| --- | --- |
| `ridge.pipeline.ExtractionResult.output_scale` | Output pixels per photo pixel (needed for physical scaling). No pixel changes |
| `ridge.export` | `to_comparison` (dark ridges on light), `mirror` (contact orientation), `ScaleEstimate`, `scale_from_ruler` (two points, ±1 px click error), `scale_from_ridge_period` (assumed 0.47 mm, ±15 %), `to_ppi` (bounded at 50 MP, CWE-789), `make_comparison_export`, `encode_png` (pHYs only, no other metadata) |
| `ridge.quality.nfiq2` | Adapter for the NIST NFIQ 2 CLI: absolute path, argv list, no shell, timeout, output ≤ 1 MiB parsed strictly (integer or CSV `QualityScore`), private temporary copy in a caller-given folder, typed "not computed" results |
| `ridge.case.export_step` | Stores the comparison export as an `export` artefact; records transforms, scale method, uncertainty and the assumed ridge distance; records an impossible scale as "not produced" without failing the job; runs NFIQ 2 when configured, labelled indicative, and removes its `work` folder |
| `ridge-case extract` | `--ruler X1 Y1 X2 Y2 MM` (single evidence only), `--no-export`, `--no-mirror`, `--ppi`, `--nfiq2 PATH`, `--nfiq2-arg` |
| Job report | New `export` and `quality` fields, `measurements.output_scale`, and `parameters.export` |

Out of scope:

- ANSI/NIST-ITL / ISO/IEC 39794 / WSQ exchange formats (OQ-4).
- Minutiae (M3).
- GUI ruler calibration (FR-51, M4).

## 2. Evidence

```bash
# integration worktree, Windows x86-64
python -m ruff check . ; python -m ruff format --check . ; python -m mypy     # clean (59 source files)
python -m pytest tests/test_case_export.py tests/test_case_store.py          # 30 passed
# m2-export alone (sub-agent): 275 passed, 3 skipped; new modules 100% covered; bandit clean
```

The full gate run on the integrated branch is recorded in the PR.

**Review follow-up (PR #4, automated Codex review of `0bcbaf8`):**

| Finding | Change |
| --- | --- |
| P1 invalid export settings failed after artefacts were stored, leaving an open job | Settings are validated before `job.start` (`validate_job_settings`); any failure after `job.start` closes the job with `job.end failed` (safe message or exception type only). Tests: `test_invalid_settings_are_refused_before_the_job_starts`, `test_any_failure_after_start_closes_the_job` |
| P2 NFIQ 2 scored non-500-ppi exports | Recorded as not computed unless the export is 500 ppi. Test: `test_nfiq2_is_skipped_unless_the_export_is_500_ppi` |
| P2 NFIQ 2 output buffered before the size check | Output is read while the tool runs and the tool is killed at the 1 MiB cap or the timeout. Test: `test_endless_output_is_cut_off_while_running` |

## 3. Forensic impact

- Print pixels are unchanged. The export is a new artefact, and a test checks it equals the library's `make_comparison_export` for the same photo.
- Export pixels depend on the scale estimate, so every report records the scale method, uncertainty and transforms.
- The ridge-period default is an **assumption** (new profile exception) until validation replaces it.
- NFIQ 2 scores are labelled "indicative only" (existing profile exception). The NIST tool's real output format and `--version` flag are **not verified**: no NFIQ 2 installation was available, and the parser accepts only a bare integer or a CSV `QualityScore` column.

## 4. Open items

- Verify the NFIQ 2 adapter against a real installation (NIST NFIQ 2 v2.3).
- Validate the 0.47 mm ±15 % assumption, or require a ruler for casework.
- `ridge` (R&D mode) does not produce comparison exports; use `ridge-case`.

## 5. First thing to do

Run `python tools/gate.py all`. Then read `src/ridge/case/export_step.py` and `src/ridge/export/transforms.py`.
