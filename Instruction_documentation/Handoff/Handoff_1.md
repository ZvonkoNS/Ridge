# Handoff_1.md

Date/time (ISO 8601 with offset): 2026-10-16T22:20+02:00
Author/agent: Claude Code (claude-opus-5-5), working with the repository owner
Project: Ridge
Branch: `main` (local only; no remote configured yet)
Base commit: `3441cf8` Add fingerprint extraction script (restored from `Ridge.bundle`)
Latest commit: `3441cf8`. **All work below is uncommitted** in the working tree.

## 1. Scope

Requested change:

1. Restore the project from `Ridge.bundle`.
2. Adopt the reusable instruction pack and adapt it to Ridge.
3. Write a detailed PRD and architecture after a discovery round with the owner.
4. Do a behaviour-preserving refactor into a typed package.
5. As a separate step, harden the security issues found. The owner asked for "the highest possible coding and OWASP standards".

Completed work:

- **Repository:** restored from the bundle; the pack was moved to the repo root (`AGENTS.md`, `CLAUDE.md`, `Instruction_documentation/`).
- **Pack adaptation:** every pack file adapted to Ridge, with editions verified on 2026-10-16 (sources in `references.md`). New files:
  - `Project_Standards_Profile.md`
  - `forensic_evidence_and_biometric_data_standards.md`
  - `desktop_gui_tauri_standards.md`
- **`docs/prd.md` v0.2:** forensic casework under the LED; requirement IDs, milestones M0–M5, risks, open questions OQ-1 to OQ-14, traceability.
- **`docs/architecture.md`:** IEEE 1016-style. Covers the module rules, STRIDE threat model, case-store and crypto design, and ADR-001 to ADR-008.
- **Refactor (step 1):** the 413-line script became the typed `src/ridge` package (largest module 184 lines). Output is bit-identical to v0 on 8 golden cases plus 4 debug images and 2 error cases, with references generated from commit `3441cf8` by `tools/make_golden.py`. `fingerprint_extract.py` remains as a v0-compatible shim.
- **Hardening (step 2):**
  - Pillow-only decoding with a format allow-list (EPS/Ghostscript, PSD and GIF are no longer reachable).
  - Byte, pixel and minimum-side limits with hard caps.
  - Typed errors; no swallowed decoder errors.
  - Atomic no-clobber publishing and `--overwrite`.
  - No metadata copied into outputs.
  - Skipped files reported; symlinks not followed.
  - Pipeline memory bounds (CWE-789: v0 could try to allocate many GiB for a thin or empty skin mask).
  - Library argument validation; exit code 3 for internal errors.
  - Headless OpenCV.
- **Tooling:**
  - `pyproject.toml` with ruff, mypy strict, pytest/coverage and bandit configuration.
  - Universal hash-pinned `requirements.lock` / `requirements-dev.lock` (uv).
  - `tools/gate.py` with 10 gates and `.gitleaks.toml`.
  - GitHub Actions (CI matrix, CodeQL, gitleaks, dependency review, Scorecard; actions pinned by SHA) and Dependabot.
  - README rewritten; unpinned `requirements.txt` removed (`git rm`, staged).

Out of scope (not done):

- **Encrypted case store, custody log, signed reports (M1).** The owner asked for the "unencrypted outputs" issue to be fixed in this step. It was deliberately not implemented as a quick fix: encrypting outputs without the case store, key custody and an export path would make outputs unusable to the examiner, and the key design needs Security Owner decisions (OQ-9, OQ-12, OQ-13). It is the first M1 item; the interim control is OS full-disk encryption (profile exception).
- M2–M5, the GUI, and any processing of real images.

## 2. Current repository state

Git status summary: 17 entries. Modified: `.gitignore`, `README.md`, `fingerprint_extract.py`. Deleted (staged): `requirements.txt`. New and untracked:

- `.github/`, `.gitleaks.toml`
- `AGENTS.md`, `CLAUDE.md`, `Instruction_documentation/`, `docs/`
- `pyproject.toml`, `requirements-dev.in`, `requirements-dev.lock`, `requirements.lock`
- `src/`, `tests/`, `tools/`

`Ridge.bundle` is excluded locally through `.git/info/exclude`.

Recent commits: `3441cf8` only.

A snapshot of the refactor-only state (before hardening) exists outside the repository in the session scratchpad. The two steps can therefore still be committed separately if the owner wants that.

## 3. Standards applicability and evidence

Project standards profile updated: yes. Four exceptions closed or partly closed (legacy script, legacy decoding, overwrite, unpinned dependencies); two added (`pillow-heif` bundled licences; bit-identical goldens only on the reference platform).

| Standard/control/rule | Applies? | Evidence produced | Exception/deviation |
| --- | --- | --- | --- |
| OWASP ASVS 5.0.0 L3 (file handling, validation, config, data protection) | Yes | `tests/test_image_io.py`, `tests/test_hardening.py`, `tests/test_offline.py`; architecture §9.1 | Server-only chapters N/A (profile) |
| OWASP Top 10:2025 / CWE Top 25 2025 | Yes | Fixed: CWE-20, CWE-22, CWE-59, CWE-367, CWE-390, CWE-400, CWE-409, CWE-434, CWE-770, CWE-789 | — |
| NIST SP 800-218 SSDF v1.1 | Yes | Hash-pinned locks, SAST, secret scan, dependency audit, SBOM, CI | Rev. 1 is still a draft |
| PEP 8/257/484, mypy strict | Yes | ruff and mypy clean (28 source files) | — |
| ISO/IEC 25010 maintainability | Yes | Modules ≤ 300 lines; 97.4% branch coverage | — |
| ISO/IEC 14764 regression protection | Yes | Golden characterization from v0 | Bit-identical only on the reference platform |
| ISO/IEC 27037/27042, ISO/IEC 17025 7.2.2 | Yes (M1/M5) | Design only (architecture §8) | Profile exceptions |
| LED / ZVOPOKD / AI Act | Yes | PRD §5, OQ-1 to OQ-3 | Legal confirmation pending |

Standards checks or tools run (Windows 11, Python 3.13.5, `.venv`):

```bash
python tools/gate.py all
# === all 10 gate(s) passed: docs, lint, format, typecheck, test, sast, deps, secrets, licenses, sbom
# test: 106 passed, 2 skipped (POSIX-only permission tests) in 71.79s; coverage 97.39% (fail-under 90)
# deps: pip-audit "No known vulnerabilities found" for requirements.lock and requirements-dev.lock
# secrets: gitleaks "no leaks found" (working tree and history)
python -m pip install --require-hashes --no-deps -r requirements.lock -r requirements-dev.lock   # OK; pip check clean
```

Exceptions, deviations or evidence gaps:

- The CI workflow has been written but **never run**: there is no GitHub remote yet. Linux, macOS, Python 3.12 and 3.14 are therefore unverified.
- The SBOM tool warns that the root component has no dependency graph entries (the SBOM is still produced).

Steps outside coding work (validation, DPIA, legal, owner approvals):

- Name the five owners (OQ-10; release blocker).
- DPIA and legal basis (OQ-1, OQ-2).
- AI Act assessment, including NFIQ 2 (OQ-3).
- AFIS exchange format and ANSI/NIST-ITL edition (OQ-4).
- `pillow-heif` licence review (OQ-14).
- Method validation (M5).

## 4. Forensic impact

Output pixels changed: **no**. Refactored and hardened code is bit-identical to v0 on all golden cases (`tests/test_characterization.py`, exact mode on this platform).

Defaults or recorded parameters changed:

- Pixel limit 150 MP and file limit 200 MiB (new).
- Existing outputs are no longer replaced without `--overwrite` (new default).
- Degenerate inputs that v0 tried to process (finger region under ~75 px, work area over 40 MP) now fail with typed errors.

Revalidation decision required / recorded: none needed for M0, because valid inputs give identical outputs. Record it when M5 begins.

Examiner-facing wording changed: README and CLI messages were checked; no claim of identification or validation is made, and the README states "not yet validated or approved for casework".

Data classes touched and how class E data stayed out of the repository and session: only synthetic images were generated (`tests/synthetic.py`). No real photos were opened. `.gitignore` now also blocks GIF, WSQ and ANSI/NIST files, and the `docs` gate fails on any tracked image.

## 5. Files changed

| File | Purpose of change |
| --- | --- |
| `AGENTS.md`, `CLAUDE.md`, `Instruction_documentation/**` | Adapted pack, standards profile, forensic and GUI standards, this handoff |
| `docs/prd.md`, `docs/architecture.md` | Product requirements and architecture |
| `src/ridge/**` | Typed package: `arrays`, `errors`, `image_io`, `debug`, `cli`, `legacy`, `pipeline/{imgutil,mask,period,gabor,quality,extract}` |
| `fingerprint_extract.py` | v0-compatible shim |
| `tests/**` | Synthetic data, golden cases and arrays, unit, CLI, hostile-input, hardening and offline tests |
| `tools/make_golden.py`, `tools/gate.py` | Golden regeneration from git history; quality gates |
| `pyproject.toml`, `requirements*.{in,lock}` | Packaging, tool configuration, hash-pinned locks |
| `.github/workflows/{ci,scorecard}.yml`, `.github/dependabot.yml`, `.gitleaks.toml`, `.gitignore`, `README.md` | CI, supply chain, ignore rules, documentation |
| `requirements.txt` | Removed (unpinned; superseded by the locks) |

## 6. Data store, records and formats

- Case-store, custody-log or report format changes: none implemented. The design is in architecture §8 and is proposed in ADR-004, ADR-005 and ADR-008.
- Migrations and recovery notes: not applicable.
- Run-record or export format changes: none.
- Write paths added or changed: W2 and W3 now go through `image_io.publish` (atomic, no-clobber), and R1 through bounded `load_image`. `direct_mutation_authorization_audit.md` findings F-1 to F-5 are updated.

## 7. Configuration, keys and CI

- New CLI options: `--overwrite`, `--max-input-mb`, `--max-megapixels`, `--verbose`. No `RIDGE_*` variables are implemented yet.
- Key-custody or signing changes: none (M1).
- CI: new workflows. Top-level `permissions: contents: read`; CodeQL and Scorecard jobs get `security-events: write`; all actions are pinned by commit SHA; gitleaks is downloaded and checksum-verified.

## 8. Security

- Decoder, limit or allow-list changes: see §1. Hard caps are 1 GiB and 170 MP. Allowed formats are JPEG, PNG, TIFF, BMP, WebP and HEIF.
- Trust-boundary changes: none. Offline behaviour is guarded by tests (no network imports; socket calls blocked during a full run).
- Threat-model notes: STRIDE table in architecture §9.2.
- Open security risks:
  - Unencrypted outputs until M1 (exception).
  - Native decoders (libjpeg, libpng, libtiff, libwebp, libheif) remain the main attack surface. Fuzzing is not yet in place.
  - `pillow-heif` bundles GPL/LGPL code (R-12).

## 9. Tests

Tests added or updated: `tests/test_characterization.py`, `test_pipeline_units.py`, `test_cli.py`, `test_image_io.py`, `test_hardening.py`, `test_offline.py`; fixtures in `conftest.py`, `synthetic.py` and `golden_cases.py`; golden data in `tests/golden/v0.{npz,json}`.

Commands run: see §3.

Determinism and golden results: exact (bit-identical) on Windows with numpy 2.5.4, OpenCV 5.0.0 and Pillow 12.3.0. Other platforms use the ≥ 99.9% pixel-agreement rule, which has not run yet.

Tests not run and why:

- POSIX permission tests (2): skipped on Windows.
- CI matrix: no remote yet.
- `python tools/gate.py` under Python 3.12 and 3.14: not installed locally.

Required tests still missing:

- Property-based fuzzing of `decode_image`.
- NFR-1 performance and memory measurement at the default limits (needs the reference workstation, OQ-11).
- Refusing an output folder inside an input folder (W1).

## 10. Release readiness

Release type: internal engineering build only.

Ready: no.

Blockers:

- Owners not named.
- Encrypted case store, custody log and signed reports (M1).
- CI never run.
- DPIA, legal basis and method validation (M5).

Rollback or mitigation: `git checkout 3441cf8 -- fingerprint_extract.py` restores v0. Everything else is additive.

## 11. Open risks and known issues

- Same-stem inputs (`a.jpg`, `a.png`): the second now fails with "already exists" instead of silently overwriting. Unique naming arrives with the case store.
- The output folder is still created before inputs are validated (v0 order).
- R-1 to R-12 in `docs/prd.md` §14.

## 12. Recommended next work

1. Commit this work (ideally as two commits: refactor, then hardening), push to GitHub and get the CI matrix green on all three OSes.
2. M1: encrypted case store, key custody, custody log, signed reports and `verify`, after Security Owner input on OQ-9, OQ-12 and OQ-13.
3. Add property-based fuzzing for `decode_image`, and measure NFR-1.
4. Decide on `pi-heif` versus `pillow-heif` (OQ-14).

## 13. First thing the next agent/developer should read or do

- Run `python tools/gate.py all` to confirm the baseline.
- Then read `docs/prd.md` §7–§8.3 and `docs/architecture.md` §8–§9 before starting M1.
