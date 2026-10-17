# Handoff_14.md

Date/time (ISO 8601 with offset): 2026-10-17T12:40+02:00
Author/agent: Claude Code (claude-opus-5-5)
Project: Ridge
Branch: `ci-minimal` → `main`
Base commit: `7b405b3` (Merge pull request #12)

## 1. Scope

Requested change: the product owner asked to "keep the use of github actions to minimum". The account's Actions spending limit was reached twice on 2026-10-17.

Completed work:

| Workflow | Before | After |
| --- | --- | --- |
| `ci.yml` | 3 OS × Python 3.12–3.14 (9 gate jobs, 3 of them macOS at about 10× the Linux rate) plus 2 Linux jobs, on every pull request and every push to `main` | **Pull requests:** 1 Linux gate job (Python 3.12, the oldest supported) plus 1 job for deps, SBOM and gitleaks (secrets merged into it). Documentation-only pull requests (`**.md`, `docs/**`, `Instruction_documentation/**`) run nothing. **No run on push to `main`:** the pull-request run already tested the merge result. **Full matrix:** on demand (Actions → CI → Run workflow, `full` = true) and for release tags `v*` |
| `arm64.yml` (new) | — | Apple silicon, Python 3.13, pixel-relevant tests only. Runs only when a pull request changes pixel-affecting code or data (pipeline, export, minutiae, image I/O, legacy, goldens, the lock file), which keeps the NFR-3 per-architecture evidence where it matters |
| `golden.yml` | On demand, plus pull requests that touched golden inputs (3 OS) | On demand only (goldens change only with an ADR and human approval) |
| `scorecard.yml` | Every push to `main`, plus weekly | Monthly, plus on demand. It is still skipped on this private repository without code scanning |
| `dependabot.yml` | Weekly, one pull request per package | Monthly and grouped: at most one pull request per ecosystem |

Docs aligned:

- PRD NFR-3 and NFR-5 acceptance criteria;
- `testing_and_codex_quality_gates.md` (agents do not re-run CI in bulk);
- `coding_standards.md`;
- `release_readiness_checklist.md` (the full matrix is required for every release);
- `Project_Standards_Profile.md` (golden evidence row, and a **new exception** with risk, compensating controls and the owner's approval).

Out of scope: no product code changed.

## 2. Evidence

- All five YAML files parse (PyYAML).
- The matrix expression: release tags and `full` = true give the 3 × 3 matrix. Anything else (pull requests, `full` = false) gives `ubuntu-latest` / 3.12.
- Local `python tools/gate.py all`: see the pull request.
- No new third-party action is used. `arm64.yml` reuses the SHA-pinned `checkout` and `setup-python`.

## 3. Standards and forensic impact

- **Testing evidence:** the per-pull-request matrix is reduced. This is recorded as a profile exception. The compensating controls are:
  - the local Windows gate before every push;
  - Linux CI on every code pull request;
  - arm64 pixel tests on pixel-affecting pull requests;
  - the full matrix required for every release.
- **Forensic impact:** none on outputs. Per-architecture reproducibility (NFR-3) is still verified on arm64 whenever pixel-affecting code changes, and on every platform per release.

## 4. Open items

- The Actions billing limit must be raised or reset by the owner before the next CI run.
- Running the full matrix before the first release is a release-checklist item.

## 5. First thing to do

Before a release, run CI manually with `full` = true. For day-to-day work, `python tools/gate.py all` locally is the main gate.
