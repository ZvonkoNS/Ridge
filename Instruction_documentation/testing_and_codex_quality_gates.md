# Testing And Coding-Agent Quality Gates

Last verified: 2026-10-16
Default test matrix for coding agents (Claude Code and others), CI and human review. The file name is kept for cross-references; "codex" here means any coding agent.

## Core testing rule

Every change is tested before it is proposed for merge. Coding agents must not claim tests passed unless the exact command ran successfully in the current workspace.

When a command cannot run (missing tool, platform, licensed analyzer, real data that must not be used, time), record the exact command, the reason and the risk in the verification summary and the handoff.

## Standards posture

- ISO/IEC/IEEE 29119 for test process and documentation; IEEE 730 and IEEE 1012 for quality assurance and method V&V before the Ops gate.
- OWASP ASVS 5.0.0, OWASP Top 10:2025, CWE Top 25 (2025), NIST SSDF and ISO/IEC 27034 for security verification.
- ISO/IEC 17025 7.2.2 and ISO/IEC 27041 for method validation; ISO/IEC 19795-1 for benchmark design; ISO/IEC 29794-4 / NFIQ 2 for quality indication.
- Language checks from `coding_standards.md`.

## Coding-agent validation behaviour

Coding agents must:

- Read `AGENTS.md` and the reading order before editing; identify applicable standards and forensic impact before planning tests.
- Propose a test plan before high-risk changes (any change to `src/ridge/pipeline/`, `image_io.py`, hashing, custody, reports, keys, sidecar or GUI IPC).
- Add or update tests with the change; run targeted tests first, then `python tools/gate.py all`.
- Use synthetic data only. Never request, read, attach or generate tests from real finger photos, case material or the volunteer set.
- Never update golden arrays (`tests/golden/*.npz`) to make a test pass. A golden update is a method change and needs an ADR and human approval.
- Never add `skip`, `xfail`, `noqa`, `type: ignore` or coverage exclusions without a written reason in the code and the handoff.
- Review the diff for security, determinism, forensic rules and unintended behaviour changes; produce the verification summary below.
- Preserve failing output that explains a real issue; record blocked verification in the handoff.

## Manual review exercises

Use for review and high-risk tasks:

- Algorithmic: ridge-period estimation from patch spectra, structure-tensor orientation, Gabor bank gain normalisation, quality map (directional energy share times periodicity), region selection morphology, crop/scale bookkeeping between working and output resolution.
- Debugging scenarios: truncated JPEG, CMYK JPEG, 16-bit PNG, alpha channel, palette image, multi-frame TIFF, EXIF orientation 1-8, grayscale photo, skin-coloured background, HEIC without pillow-heif, non-ASCII Windows path, output name collision, output directory inside input directory, hash mismatch after copy, broken custody chain, result change with a different OpenCV thread count or dependency version.
- Threat-model review: decoding boundary, file system writes, key handling, sidecar and IPC boundary, export formats, update channel.
- Forensic review: does the change alter pixels, defaults or wording? Could it create or remove ridge detail? Is the examiner told?

## Automated test taxonomy

### Static and build validation

- Lint, format check, `mypy --strict`, documentation integrity (`docs` gate), runtime-import boundary (runtime code never imports `docs/` or `Instruction_documentation/`), dead-code and circular-import checks where tooling exists.

### Static security analysis

- SAST (bandit, ruff `S`, CodeQL in CI), secret scanning (gitleaks), dependency vulnerabilities (pip-audit on `requirements.lock`, GitHub dependency review), license allow-list, CWE IDs on findings.
- Not applicable to Ridge today: MISRA, CERT C/C++, HIC++, BARR-C, JPL, JSF, AUTOSAR checks (no project C/C++); container scanning (no containers).

### Unit tests

- Pure pipeline functions on synthetic arrays: period estimation recovers a known period within tolerance; orientation recovers a known angle; Gabor kernels have zero DC and unit gain; quality map is high on clean synthetic ridges and low on noise; mask behaviour on skin-like vs uniform backgrounds.
- Validators, limit checks, path builders, name-collision handling, error mapping, hashing helpers, canonical JSON, timestamp formatting.

### Integration tests

- CLI end to end on synthetic files in a temporary directory: outputs created, exit codes, messages, no overwrite without `--overwrite`, refusal of unsafe output directories.
- `fingerprint_extract.py` shim behaves like `python -m ridge` for documented options.
- From M1: case store create/open/ingest/process/export/delete; custody log written for each action; key wrap/unwrap with test keys only.
- From M4: sidecar JSON-RPC handlers driven through stdio.

### Contract tests

- Run record, job report, custody entry and JSON-RPC message schemas; ECMA-404 validity; RFC 8785 canonical bytes stable; ISO 8601 UTC timestamps; unknown fields rejected; backward compatibility of report verification.

### Hostile input and decoder tests (M0)

- Malformed and truncated files for every allow-listed format.
- Wrong extension vs content; disallowed formats (EPS, PDF, PSD, SVG) rejected before any decoder runs.
- Oversized files (byte limit), huge dimensions with small files (decompression bombs: PNG, TIFF, WEBP, HEIF), many frames, zero-size and 1x1 images, extreme aspect ratios.
- Errors are typed, no fallback decoder runs, no partial output remains, memory stays within budget.

### Fuzz and property tests

- hypothesis property tests: pipeline functions accept any finite array within limits without NaN output; path builders never escape the output directory; canonical JSON round-trips; custody verification rejects any single-field mutation.
- Coverage-guided fuzzing of the decode boundary with atheris where it supports the CI Python version (scheduled job, not per pull request); otherwise a hypothesis-based harness. Crashes and hangs are release blockers.

### Forensic validation tests

| Test | Where | Rule |
| --- | --- | --- |
| Golden characterization | `tests/test_characterization.py`, in `test` gate | Two checks on synthetic inputs: (1) v0 loaded from git history runs next to the package on the same machine, and results must be bit-identical on every platform; (2) stored per-architecture goldens `tests/golden/v0-<arch>.*` must match exactly on the reference machine and within documented same-architecture tolerances elsewhere; (3) the committed golden sets of different architectures must stay inside the cross-architecture envelope (`tests/test_cross_architecture.py`). |
| Determinism | `test` gate | Same input twice in one process and in two separate processes gives identical output pixel hash and file hash; varying `cv2.setNumThreads` either gives identical results or is pinned. |
| Reproducibility record | `test` gate | Run record contains every field required by `forensic_evidence_and_biometric_data_standards.md` section 6 and hashes match re-read files. |
| Evidence immutability | `test` gate | Input bytes and modification time unchanged after processing; outputs never written beside originals. |
| Metadata minimisation | `test` gate | Outputs contain no EXIF/XMP/ICC text or GPS from inputs. |
| Custody and report integrity (M1) | `test` gate | Valid chains and signatures verify; tampered, reordered, truncated, wrong-key and modified reports fail. |
| Matcher benchmark (Ops gate) | Outside CI, volunteer set | SourceAFIS or NBIS Bozorth3; FNMR at the fixed FMR from the validation plan with confidence intervals; per-subgroup results. |
| NFIQ 2 (M2 / Ops gate) | Adapter tests in CI on synthetic data; score study outside CI | Adapter returns errors for out-of-scope inputs; thresholds only from the validation study. |

The volunteer set never enters CI, the repository or a coding-agent session.

### Regression tests

- Every fixed bug gets a failing test first. Golden set and CLI behaviour protect unchanged behaviour during the refactor.

### End-to-end and smoke

- CLI smoke on synthetic data on Windows, Linux and macOS runners.
- GUI E2E from M4 (`desktop_gui_tauri_standards.md` section 12).

### Not applicable today (with trigger)

| Category | Status |
| --- | --- |
| Authorization, RLS, cross-tenant tests | Not applicable: single examiner, no shared store. Trigger: lab server or multi-user store. From M4, IPC allow-list denial tests take this role. |
| Schema/migration tests | Not applicable until the case store exists (M1); then migrations apply cleanly, are versioned, and old cases open or fail with a clear error. |
| Component/UI, accessibility, visual tests | From M4. |
| Webhook, provider, payment, AI-output tests | Not applicable: no network, no providers, no AI components. Trigger: any of these is added (AI also triggers the AI Act reassessment). |
| Load tests for public endpoints | Not applicable: no endpoints. A local performance benchmark (time and peak memory per megapixel) is recommended, not a gate. |

## Quality gates

Single entry point: `python tools/gate.py <gate>` (implemented by `tools/gate.py`). `all` runs locally before every push. To keep GitHub Actions usage minimal (owner decision 2026-10-17), CI runs the gates on pull requests with one Linux job (Python 3.12) plus the supply-chain gates, skips documentation-only pull requests, adds Apple silicon pixel tests (`arm64.yml`) only when pixel-affecting code changes, and runs the full Windows/Linux/macOS x Python 3.12-3.14 matrix on demand and for release tags.

| Gate | Tool | Checks | Release blocker |
| --- | --- | --- | --- |
| `docs` | gate script | Required docs exist; every path in the `AGENTS.md` reading order exists; handoffs are consecutive (`Handoff_1.md`, `Handoff_2.md`, ...); runtime code never imports `docs/` or `Instruction_documentation/` | Yes |
| `lint` | `ruff check` | Rule set in `coding_standards.md` | Yes |
| `format` | `ruff format --check` | PEP 8 formatting | Yes |
| `typecheck` | `mypy --strict` (config in `pyproject.toml`) | Typing | Yes |
| `test` | pytest + coverage with `fail-under` | All tests above that run in CI | Yes |
| `sast` | bandit | Python security findings | Yes (findings need fix or documented exception) |
| `deps` | pip-audit against `requirements.lock` (and `requirements-dev.lock`) | Known vulnerabilities | Yes |
| `secrets` | gitleaks | Secrets in tree and history | Yes |
| `licenses` | pip-licenses with allow-list | Licenses compatible with internal proprietary distribution, including bundled native libraries | Yes |
| `sbom` | CycloneDX | SBOM generated for the release | Yes for releases |
| `all` | all of the above | | Yes |

Coverage threshold is configured in `pyproject.toml`. Pack minimum: 90 percent line and branch coverage for `src/ridge/`, and every error path of `src/ridge/image_io.py` covered. Lowering it is a profile exception.

Also in CI (GitHub Actions, actions pinned by commit SHA, minimal `permissions`): CodeQL, dependency review, gitleaks, OpenSSF Scorecard (monthly). Agents do not re-run CI in bulk; they re-run only the runs a merge needs.

Future GUI gates (M4): `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run test:e2e`, `npm audit --audit-level=moderate`, `cargo clippy -- -D warnings`, `cargo audit`, `cargo deny check`.

### Pack command mapping

| Pack command | Ridge equivalent |
| --- | --- |
| `npm run test:docs` | `python tools/gate.py docs` |
| `npm run test:security-hardening` | `python tools/gate.py sast` plus the hostile-input and security tests in `test` |
| `npm run test:schema-drift` | Not applicable today (no schema). From M1: case-store schema and migration tests in `test` |
| `npm run lint` | `python tools/gate.py lint` |
| `npm run typecheck` | `python tools/gate.py typecheck` |
| `npm run test` | `python tools/gate.py test` |
| `npm run build` | Wheel build for releases (`docs/architecture.md` section 10: wheel plus hashed lock for M0-M3, Tauri bundle from M4); not a named gate in `tools/gate.py`; from M4 also `npm run build` for the GUI |
| `npm run test:e2e` | CLI smoke tests in `test`; GUI `npm run test:e2e` from M4 |
| `npm audit --audit-level=moderate` | `python tools/gate.py deps`; npm audit itself from M4 |
| `npm run format:check` | `python tools/gate.py format` |
| `npm run test:unit`, `test:integration`, `test:regression`, `test:contracts`, `test:property` | `python tools/gate.py test` (pytest markers, if defined in `pyproject.toml`, select subsets locally) |
| `npm run test:component`, `test:accessibility` | From M4 in `gui/` |
| `npm run test:functions` | Not applicable (no serverless). JSON-RPC handler tests in `test` from M4 |
| `npm run test:authz` | Not applicable (single user). IPC allow-list denial tests from M4 |
| `npm run test:storage`, `test:migrations` | `test` from M1 (case store) |
| `npm run test:performance` | Not a gate; local benchmark recommended |
| `npm run test:visual` | Not applicable; golden arrays cover output regression |
| `npm run test:fuzz` | hypothesis harness in `test`; scheduled atheris job |
| `npm run scan:secrets` | `python tools/gate.py secrets` |
| `npm run scan:licenses` | `python tools/gate.py licenses` |
| `npm run scan:sast` | `python tools/gate.py sast` (and CodeQL in CI) |
| `npm run scan:deps` | `python tools/gate.py deps` (and dependency review in CI) |
| `npm run scan:containers` | Not applicable (no containers) |
| `npm run standards:check` | `python tools/gate.py docs` for structural checks; standards evidence is reviewed manually against `Project_Standards_Profile.md` |
| `npm run sbom` | `python tools/gate.py sbom` |

Do not merge or release if any required gate exits non-zero.

## Risk-based minimum test matrix

| Risk level | Ridge examples | Minimum verification |
| --- | --- | --- |
| Low | Docs, comments, CLI help text without behaviour change | `docs`, `lint`, `format` |
| Medium | CLI options, messages, configuration loading, non-pipeline refactors | Targeted tests plus `python tools/gate.py all` |
| High | Pipeline, decoding, limits, output writing, hashing, dependency upgrades that touch pixels | Full gate, golden and determinism tests, hostile-input tests, forensic review, revalidation decision |
| Critical | Case store, custody log, signatures, key custody, export formats, GUI IPC, update channel | Full gate, threat-model update, independent review, rollback/recovery notes, owner approval |
| Ops gate | First operational use or a method change after validation | Approved validation report, DPIA, AI Act assessment, signed release, all owners named |

## Required verification summary format

```text
Verification:
- Standards considered:
  - <standard/control/rule or "no new applicability">
- Forensic impact: none / pixels changed / defaults changed / wording changed (+ ADR link)
- Added/updated tests:
  - <test file or description>
- Commands run:
  - <exact command> -> pass
- Not run:
  - <exact command> - <reason and risk>
- Determinism/golden checked: yes/no + notes
- Evidence integrity checked: yes/no + notes
- Standards exceptions: none / listed
- Unchanged behaviour protected: yes/no + notes
```
