# Handoff_8.md

Date/time (ISO 8601 with offset): 2026-10-17T09:45+02:00
Author/agent: Claude Code (claude-opus-5-5), autonomous development window
Project: Ridge
Branch: `m5-validation-metrics` (built on `m4-sidecar`) → PR into `main` after PRs #5 and #6

## 1. Scope

An **M5 enabler**: metrics for the method validation study (PRD §12), following ISO/IEC 19795-1.

| Part | What |
| --- | --- |
| `ridge.validation.metrics` | FMR/FNMR per threshold (accept when score ≥ t). Operating point at a target FMR: lowest threshold with FMR ≤ target. Wilson 95 % intervals, exact at 0 errors and at all errors. Rule-of-30 sufficiency flag. DET curve (thinned), EER estimate, failure-to-extract rate. All O(n log n) via sorted arrays |
| `ridge.validation.report` / `ridge-validate` | Strict score-CSV reader (`genuine`, `score`, optional `group`; ≤ 512 MiB; ≤ 50 groups; finite scores); JSON report `ridge.validation/1` with overall and per-group results; refuses to overwrite an existing report |

## 2. Evidence

`tests/test_validation_metrics.py` covers:

- hand-computed operating points (threshold 0.6, FMR 1/10, FNMR 1/5);
- strict targets;
- rule of 30 with 30 000 impostor comparisons;
- Wilson bounds;
- EER and DET monotonicity;
- 1 000 000 impostor comparisons in under 20 s;
- invalid inputs and malformed CSVs;
- groups;
- the CLI.

**NFR-1 baseline (`tools/perf_benchmark.py`, same branch):**

| Synthetic photo | Time (2 runs) | Peak traced memory |
| --- | --- | --- |
| 12 MP, ridge spacing 16 px | 7.7–8.5 s | 387 MiB |
| 12 MP, ridge spacing 24 px | 4.6–4.8 s | 386 MiB |
| 48 MP, ridge spacing 32 px | 9.6–9.7 s | 695 MiB |

Measured on the development workstation (Intel x86-64, Windows 11, OpenCV 14 threads). This is within the NFR-1 targets (p95 ≤ 20 s and ≤ 4 GiB for 12 MP). Repeat on the reference workstation (OQ-11).

**Review fixes (PR #7):**

- With a `group` column, every row needs a group.
- `all` is reserved.
- A group without both genuine and impostor comparisons is refused instead of silently dropped from the bias check.
- The CSV is read through `read_bounded`: regular files only, with the size enforced while reading.
- CSV parser errors become validation errors.

## 3. Forensic impact

- None on case processing.
- The tool is for the lab's validation study. Its intervals assume independent comparisons, which repeated fingers violate, so they are optimistic. This is stated in the module and the report.

## 4. Open items

- The matcher run itself (SourceAFIS or NBIS) and the consented dataset are outside the repository (OQ-6, OQ-7).
- Targets are to be confirmed after the baseline run (OQ-7).

## 5. First thing to do

Run `python tools/gate.py all`. Then read `src/ridge/validation/metrics.py`.
