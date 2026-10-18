# Release Readiness Checklist

Last verified: 2026-10-16
Use before merge to the default branch, before tagging any build, and before delivering Ridge to an examiner workstation.

## Release principle

A release is ready only when behaviour, security, forensic integrity, tests, configuration, documentation, rollback and handoff evidence are complete for its type.

| Release type | Purpose | Extra requirements |
| --- | --- | --- |
| Internal engineering build (M0-M4) | Development and testing on synthetic data | All automated gates; no casework use; label "not for casework" in version string or release notes. |
| Operational release (Ops gate, `docs/prd.md` M5) | Use on case material | Everything in this file, including the forensic release gates. |

## Standards release gate

- `Project_Standards_Profile.md` is current, including owners, editions and exceptions.
- Applicable language, security, forensic, biometric, privacy, testing and documentation standards were reviewed for the changes in this release.
- Exceptions have owner, risk, compensating control, approval and expiry; none has expired.
- No claim of certification, accreditation, validation or legal compliance appears in the product, docs or release notes unless externally supported and approved.

## Required automated gates

Run for the exact release commit; all must pass:

```bash
python tools/gate.py all
```

`all` covers `docs`, `lint`, `format`, `typecheck`, `test`, `sast`, `deps`, `secrets`, `licenses`, `sbom` (details in `testing_and_codex_quality_gates.md`).

Also required in GitHub Actions for the release commit: CodeQL, dependency review, gitleaks, OpenSSF Scorecard result reviewed, the full test matrix on Windows, Linux and macOS runners (CI run with full = true, or the release tag), since pull requests run a reduced matrix.

From M4 (GUI):

```bash
python tools/gate.py gui      # npm lint, typecheck, format, test, build, audit, licences; cargo fmt, clippy, test, audit, deny
npm run test:e2e              # Tauri WebDriver E2E: not implemented yet (standards profile exception)
python -m pip install --require-hashes --no-deps -r requirements-build.lock
python tools/build_sidecar.py # freezes the sidecar, checks the archive (keystore backend) and smoke-tests it over stdio
cd gui && npx tauri build --config src-tauri/tauri.release.conf.json   # bundle with resources/sidecar/
```

In GitHub Actions the GUI gate runs for the release tag (`gui.yml`). The frozen sidecar and the installer are code-signed before release; the bundle build has not been exercised yet (standards profile exception).

## Forensic release gates

| Gate | Internal build | Operational release |
| --- | --- | --- |
| Golden characterization and determinism tests pass on every supported platform | Required | Required |
| Pixel-changing changes have an ADR and a recorded revalidation decision by the Forensic Quality Manager | Required | Required |
| Method validation report approved (ISO/IEC 17025 7.2.2) and its scope matches this release's method and platforms | - | Required |
| DPIA approved by the DPO (LED Art. 27, to be confirmed) | - | Required |
| AI Act applicability assessment confirmed by legal | - | Required |
| All owner roles named; approvals by Product Owner, Security Owner, Quality/Release Owner, Forensic Quality Manager and DPO recorded | Owners named (exception until then) | Required |
| Reproducibility evidence: run manifest of the reference synthetic run, lock-file hash, dependency versions | Required | Required |
| From M1: custody and report verification tests pass; case-store format version and migration notes documented | Required | Required |
| Examiner documentation (use, limits, forbidden claims, artefact warning) current | - | Required |

## Release artifacts

- Built from a clean checkout of the tagged commit with hashed lock files (`pip install --require-hashes`).
- `SHA256SUMS` for every artifact and a detached signature by the release key (`environment_configuration_and_secrets.md`); OS code signing for installers (M4).
- CycloneDX SBOM for Python dependencies (and npm/Cargo from M4) attached.
- Release notes include version, commit, forensic impact (pixels changed or not), exceptions, known issues.

## Manual delivery gates

The pack's production-database and hosted-service steps (migrations on a production database, RLS/RPC checks, storage bucket policies, provider dashboards, webhook URLs, public endpoints) are **not applicable to Ridge**: there is no server, database service or network endpoint. They become applicable only if a server component is added. Equivalent checks:

- Installation on a clean offline workstation of each supported OS family: signature and `SHA256SUMS` verified before installation.
- Offline operation confirmed: a full synthetic workflow produces no network traffic (OS firewall log or monitor).
- CLI smoke test on synthetic data; `--version` reports the expected version and commit.
- From M1: an existing synthetic case created by the previous release opens, migrates (if needed) and verifies.
- Full-disk encryption active on the target workstation (interim control until M1; still required afterwards).
- `Instruction_documentation/`, `docs/` and `tests/` are not shipped in runtime packages, and runtime code does not import them.
- Rollback: previous signed release available; case-store format compatibility stated.

## Security release blockers

Block release if any is true:

- A required gate fails or was skipped without an approved exception.
- Decoding lacks the format allow-list or byte/pixel/frame limits; any decoder fallback chain exists.
- Any path can overwrite outputs without the explicit `--overwrite` flag, or can modify originals or case-store objects.
- Class E data, secrets or real images are present in the repository, artifacts, logs or test fixtures.
- Passphrases or keys can enter argv, environment, logs or reports.
- From M1: case data is written unencrypted outside explicit exports; custody or report verification fails.
- From M4: WebView capabilities exceed the allow-list, CSP is missing or permissive, remote content or an updater is enabled.
- Dependency audit shows an unaddressed vulnerability rated moderate or higher in a runtime dependency.
- Evidence required by the profile for ASVS, Top 10, CWE or SSDF is missing.

## Standards and quality release blockers

- Language versions and tool configurations not declared.
- Linter, type-checker or SAST rules disabled without written reasons.
- Coverage below the configured threshold.
- Numerical tolerance or determinism behaviour untested.
- Traceability from `docs/prd.md` requirements to tests missing for changed requirements.

## Documentation release blockers

- Docs do not match behaviour (CLI options, defaults, outputs, limits).
- Latest handoff missing for substantial work, or handoff numbering not consecutive.
- Profile stale; new configuration or environment variable undocumented.
- Write-path audit (`direct_mutation_authorization_audit.md`) not updated for new write paths.
- Product documentation imported into runtime code.

## Domain release gates

Functional-safety gates (IEC 61508, ISO 26262, DO-178C and similar) are not applicable: Ridge has no safety function. The forensic release gates above replace them. If a future scope adds a safety function, restore the pack's safety gates.

## Final release note template

```text
Release summary:
- Version / commit / release type (internal build or operational):
- Scope:
- Forensic impact (pixels changed? defaults changed? ADR link, revalidation decision):
- Standards considered and evidence:
- Exceptions (from Project_Standards_Profile.md section 8):
- Case-store format / migration notes (M1+):
- Gates passed (command and CI run link):
- Tests not run and why:
- Platforms verified:
- Artifacts, SHA256SUMS, signature, SBOM:
- Known risks:
- Rollback plan:
- Approvals (role, name, date):
```
