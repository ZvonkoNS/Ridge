# Ridge Project Standards Profile

Last verified: 2026-10-16
Derived from `Project_Standards_Profile_Template.md`. Review triggers are in section 10. Product requirements: `docs/prd.md`. Design: `docs/architecture.md` (ADR table in section 13; `docs/adr/` when created).

## 1. Project identification

| Field | Value |
| --- | --- |
| Project name | Ridge |
| Repository | GitHub (internal, private). Default branch protected. |
| Product Owner | TBD - release blocker |
| Security Owner | TBD - release blocker |
| Quality/Release Owner | TBD - release blocker |
| Data Protection Officer | TBD - release blocker |
| Forensic Quality Manager (ISO/IEC 17025) | TBD - release blocker |
| Last reviewed | 2026-10-16 |

No release beyond internal engineering builds is allowed while any owner is unnamed (see section 8).

## 2. Product and deployment context

| Field | Value |
| --- | --- |
| Product type | Offline forensic image-enhancement tool: CLI and Python library now; desktop GUI (Tauri v2 + React + TypeScript) later. Distribution: internal, proprietary, own organisation only. |
| Use | A fingerprint examiner extracts ridge images from photos supplied as case material and compares them manually against NAFIS/AFIS results (ACE-V). Ridge never identifies anyone and makes no conclusions. |
| Users and roles | One examiner per workstation (OS account plus case-store passphrase). Developers never access case data. No multi-user or tenancy. |
| Deployment environments | Offline examiner workstations on Windows 11, Linux and macOS; developer workstations; GitHub Actions CI (synthetic data only). |
| Network exposure | None at runtime: no network access, no telemetry, no auto-update. |
| Data classification | Class E (biometric, special category), C (case-confidential), I (internal), S (secrets). Definitions: `forensic_evidence_and_biometric_data_standards.md` section 2. |
| Legal regime | Law-enforcement processing under Directive (EU) 2016/680 as transposed in Slovenia by ZVOPOKD; GDPR only for non-LED processing (for example the volunteer validation set, depending on the legal basis). DPIA required. To be confirmed by the DPO/legal. |
| Regulated domain | Forensic science (ISO/IEC 17025 laboratory, ISO 21043, ENFSI). No functional-safety standard applies. |
| Risk posture | Every change to the pipeline, decoding, hashing, custody, reports, keys or exports is high risk: an undetected error can affect a criminal case. |

### Milestones

Authoritative definition: `docs/prd.md` section 7. Summary used for the tags in this pack:

| ID | Content |
| --- | --- |
| M0 | Foundation: pack adopted, PRD and architecture, behaviour-preserving refactor into the typed `src/ridge/` package with `fingerprint_extract.py` shim, input hardening (allow-list, limits, no decoder fallback, atomic writes), quality gates and CI. |
| M1 | Evidence integrity: encrypted case store, key custody, evidence import, hash-chained custody log, signed job reports, `ridge case verify`, export path, retention and legal hold. |
| M2 | Matcher-ready output: polarity and mirror conversion, 500 ppi normalisation with scale calibration, lossless export, job report fields, NFIQ 2 integration. |
| M3 | Minutiae and exchange: minutiae extraction; export in the AFIS exchange format once confirmed (`docs/prd.md` OQ-4). |
| M4 | Desktop GUI (Tauri v2 + React + TypeScript) over the stdio JSON-RPC sidecar. |
| M5 = Ops gate | Validation and approval: benchmark on the consented dataset, validation report, DPIA, AI Act assessment, all owners named and sign-off, signed v1.0 release. Required before any casework use. Separate from the engineering milestones. |

## 3. Technology profile

| Area | Technologies | Applicable standards and rules |
| --- | --- | --- |
| Core library and CLI | Python 3.12+ (development on 3.13), numpy, opencv-python-headless (processing and encoding only, `docs/architecture.md` ADR-003), Pillow, optional pillow-heif | PEP 8/257/484, `coding_standards.md`, IEEE 754 |
| Image decoding | Pillow as the only decoder with a `formats=` allow-list; pillow-heif (bundles libheif and codec libraries) for HEIF/HEIC | CWE-20, CWE-400, CWE-409, CWE-770, CWE-787, CWE-125; ASVS V5 |
| Case store (planned, M1) | Per `docs/architecture.md` section 8: files plus JSONL custody log, AES-256-GCM encrypted content-addressed blobs (ADR-008 proposed; SQLite is the documented alternative) | `backend_database_rls_rpc_standards.md`, ISO/IEC 9075 only if SQLite is chosen, ASVS V11/V14 |
| Custody log and reports (planned, M1) | SHA-256, RFC 8785 canonical JSON, Ed25519 | `forensic_evidence_and_biometric_data_standards.md` |
| Key custody (planned, M1) | OS keystore (Windows DPAPI, macOS Keychain, Linux Secret Service) plus Argon2id passphrase wrapping | `environment_configuration_and_secrets.md`, RFC 9106 |
| Sidecar (planned, M4) | JSON-RPC 2.0 over stdio | `edge_function_standards.md` |
| Desktop GUI (planned, M4) | Tauri v2 (Rust), React, TypeScript, Motion | `desktop_gui_tauri_standards.md`, ECMA-262, WCAG 2.2 AA |
| Serverless functions | None | Not applicable |
| Native components | Third-party only (OpenCV, libheif, codecs) | Supply-chain review, fuzzing at the decoding boundary |
| Scripts and tooling | `tools/gate.py`, pytest, ruff, mypy, bandit, pip-audit, pip-tools, gitleaks, pip-licenses, CycloneDX | `testing_and_codex_quality_gates.md` |
| Data formats | PNG output; JSON run records and reports; planned ANSI/NIST-ITL or ISO/IEC 39794 exports | ECMA-404, RFC 8785, ISO 8601, ISO/IEC 10646 |
| OS and runtime | Windows 11, Linux, macOS; offline | POSIX where relevant, path handling per `coding_standards.md` |
| AI/ML components | None today. NFIQ 2 (planned, M2) uses a trained model; ML minutiae extraction would be another trigger | EU AI Act assessment in the standards matrix |

## 4. Applicable standards

Editions marked "verified" were checked on 2026-10-16 against the source in `references.md`. Others must be confirmed before they are cited in a release.

| Standard or framework | Applies? | Edition/version | Scope | Required evidence | Owner |
| --- | --- | --- | --- | --- | --- |
| ISO/IEC/IEEE 12207 | Yes | Not verified - confirm | Lifecycle, configuration management | PRD, ADRs, handoffs, release records | Quality/Release Owner |
| ISO/IEC/IEEE 15288 | Partly | Not verified - confirm | Ridge as part of the lab's examination system | Interface notes to AFIS workflow | Product Owner |
| ISO/IEC 25010 / 25000 | Yes | Not verified - confirm | Quality attributes | Acceptance criteria in `docs/prd.md` | Product Owner |
| ISO/IEC 27001 / 27002 | Align (organisation ISMS) | 27001:2022 + Amd 1:2024; 27002:2022 (verified) | Access, cryptography, logging, supplier, change management | Control mapping, risk register | Security Owner |
| ISO/IEC 27034 | Yes | Not verified - confirm | Application security controls | Control mapping in reviews | Security Owner |
| ISO/IEC 5055 | Optional | Not verified - confirm | Structural quality | Static-analysis metrics | Quality/Release Owner |
| OWASP ASVS | Yes, Level 3 where applicable | 5.0.0 (verified) | Chapters mapped in the standards matrix | ASVS checklist, tests | Security Owner |
| OWASP Top 10 | Yes, as risk taxonomy | 2025 (verified) | A02, A03, A04, A05, A06, A08, A09, A10 mainly | Threat model, tests | Security Owner |
| CWE / CWE Top 25 | Yes | 2025 Top 25 (verified) | Finding classification | CWE IDs on findings | Security Owner |
| NIST SP 800-218 SSDF | Yes | SP 800-218 v1.1 final (verified); Rev. 1 (v1.2) is a draft and is not adopted | Secure development practices | SSDF practice evidence | Security Owner |
| NIST SP 800-53 | No | - | No contractual requirement | - | - |
| CERT coding standards | Where relevant | Not verified - confirm | Python has no CERT standard; CERT C/C++ concepts guide review of native dependency use | Review notes | Security Owner |
| ISO/IEC/IEEE 29119 | Yes | Not verified - confirm | Test process and documentation | Test strategy, gate output | Quality/Release Owner |
| IEEE 730 / IEEE 1012 | Yes for Ops gate | Not verified - confirm | Quality assurance, independent V&V of the method | QA records, validation report | Forensic Quality Manager |
| ISO/IEC 17025 | Yes (laboratory) | 2017, confirmed 2023 (verified) | 7.2.2 method validation, 7.5 technical records, 7.6 uncertainty, 7.11 data and software | Validation report, records | Forensic Quality Manager |
| ISO 21043 parts 1-5 | Yes | 21043-1:2025, -2:2018 (to be revised), -3:2025, -4:2025, -5:2025 (verified) | Forensic process, records, reporting | Mapping in forensic standards file | Forensic Quality Manager |
| ENFSI Best Practice Manual for Fingerprint Examination | Yes (lab practice) | Edition not verified - confirm | ACE-V, documentation | Lab procedure reference | Forensic Quality Manager |
| ISO/IEC 27037 / 27041 / 27042 / 27043 | Yes | 27037:2012, 27041:2015, 27042:2015, 27043:2015 (verified) | Evidence preservation, method suitability, analysis | Custody, hashing, validation evidence | Forensic Quality Manager |
| ISO/IEC 29794-4 and NFIQ 2 | Yes (M2) | 29794-4:2024; NFIQ 2.3.0 (verified) | Quality indication, indicative only on photo-derived images | Validation results | Forensic Quality Manager |
| ISO/IEC 39794-4 / 39794-2 | Candidate export formats (M3) | 39794-4:2019 + Amd 1:2023 (under review); 39794-2:2023 (verified) | Exports | Conformance tests | Product Owner |
| ISO/IEC 19794-4 / 19794-2 | Candidate legacy formats | 19794-4:2011 + Amd 1:2013 + Amd 2:2015, confirmed 2024 (verified); 19794-2 not verified | Exports if the AFIS requires them | Conformance tests | Product Owner |
| ANSI/NIST-ITL 1 | Candidate export format (M3) | ANSI/NIST-ITL 1-2025 (SP 500-290e4) is current (verified); the AFIS vendor may require 1-2011 Update 2015 - open question | Exports | Conformance tests against vendor spec | Product Owner |
| ISO/IEC 24745 | Yes | 2022 (verified) | Confidentiality and integrity of biometric data | Case store design, tests | Security Owner |
| ISO/IEC 19795-1 | Yes (validation) | 2021, to be revised (verified) | Benchmark design and reporting | Validation report | Forensic Quality Manager |
| ISO/IEC 30107 | Mostly not applicable | 30107-1:2023 (verified) | No capture device or enrolment; see matrix | Applicability note | Security Owner |
| Directive (EU) 2016/680, ZVOPOKD | Yes | ZVOPOKD Uradni list RS 177/2020; article-level content not verified - confirm | Legal basis, DPIA, logging, security | DPIA, records of processing | DPO |
| GDPR (EU) 2016/679 | Only non-LED processing | - | Possibly the volunteer set | DPO assessment | DPO |
| EU AI Act (Reg. (EU) 2024/1689) | Assessed: likely not an AI system today - legal to confirm | 2024/1689 verified; amendment by the "Digital Omnibus" reported, not verified | Reassess when ML components are added | Written assessment | DPO / legal |
| WCAG 2.2 / ISO/IEC 40500:2025 | Yes (M4) | Verified | GUI | Accessibility tests | Product Owner |
| Domain safety standards (IEC 61508 etc.) | No | - | No safety function | - | - |

## 5. Language and coding-standard selections

| Language | Language standard | Style/safety guide | Tooling | Required commands |
| --- | --- | --- | --- | --- |
| Python | CPython 3.12 minimum; development 3.13 | PEP 8, PEP 257, PEP 484; `coding_standards.md` | ruff, mypy --strict, pytest, bandit, pip-audit | `python tools/gate.py lint format typecheck test sast deps` (one gate per call, or `all`) |
| JSON | ECMA-404; RFC 8785 for signed or hashed JSON | Schema validation at trust boundaries | pytest contract tests | `python tools/gate.py test` |
| TOML | TOML 1.0 (`tomllib`) | `pyproject.toml`, configuration | ruff, tests | `python tools/gate.py lint` |
| SQL (only if SQLite is chosen for the case store) | ISO/IEC 9075 principles, SQLite dialect | Parameterised queries only | pytest | `python tools/gate.py test` |
| TypeScript (planned, M4) | ECMA-262, TypeScript strict | `desktop_gui_tauri_standards.md` | ESLint, tsc, Vitest | `npm run lint`, `npm run typecheck`, `npm run test` |
| Rust (planned, M4) | Rust stable, edition per `Cargo.toml` | Clippy, `forbid(unsafe_code)` | cargo clippy, cargo audit, cargo deny | `cargo clippy -- -D warnings`, `cargo audit`, `cargo deny check` |
| YAML (CI) | YAML 1.2 | Actions pinned by commit SHA, least-privilege `permissions` | actionlint (recommended), OpenSSF Scorecard | CI |
| C / C++ / C# / other | Not used in project code | - | - | - |

Note for the Quality/Release Owner: on 2026-10-16 the Python devguide lists 3.13 as security-fixes-only and 3.14 as the current bugfix branch. Development is on 3.13; CI (`.github/workflows/ci.yml`) runs 3.12, 3.13 and 3.14 on Windows, Linux and macOS.

## 6. Security assurance level

- Baseline: OWASP ASVS 5.0.0 Level 3 for every applicable requirement (mapping: `standards_applicability_and_compliance_matrix.md`).
- Threat model required: yes, maintained in `docs/architecture.md` (or a file it references). Missing threat model blocks M1.
- SAST required: yes (bandit via `python tools/gate.py sast`; CodeQL in GitHub Actions).
- DAST required: not applicable (no network endpoint). Equivalent: fuzzing of decoders and, from M4, of IPC and JSON-RPC handlers.
- Dependency audit required: yes (`python tools/gate.py deps` with pip-audit on `requirements.lock`; GitHub dependency review).
- Secret scanning required: yes (`python tools/gate.py secrets`).
- SBOM required: yes (`python tools/gate.py sbom`, CycloneDX) for every release.
- Penetration test or independent security review: yes, before the Ops gate.
- Independent review: yes, method validation reviewed by the Forensic Quality Manager; security review by someone other than the author of the change.

## 7. Testing and verification evidence

| Test or verification type | Required? | Tool/command | Release blocker? | Evidence location |
| --- | --- | --- | --- | --- |
| Lint/format | Yes | `python tools/gate.py lint`, `python tools/gate.py format` | Yes | CI log |
| Typecheck | Yes | `python tools/gate.py typecheck` | Yes | CI log |
| Unit tests and coverage | Yes | `python tools/gate.py test` | Yes | CI log, coverage report |
| Golden characterization | Yes (M0) | part of `test`, data in `tests/golden/*.npz` | Yes | CI log |
| Determinism | Yes (M0) | part of `test` | Yes | CI log |
| Hostile input (malformed, oversized, bombs, wrong format) | Yes (M0) | part of `test` | Yes | CI log |
| Fuzzing of decoders | Yes (M1) | hypothesis in `test`; atheris campaigns scheduled | Findings block | CI artifacts |
| Custody/report integrity | Yes (M1) | part of `test` | Yes | CI log |
| IPC/JSON-RPC security | Yes (M4) | part of `test` and GUI tests | Yes | CI log |
| E2E/smoke | Yes | CLI smoke on synthetic data; GUI E2E from M4 | Yes | CI log |
| Accessibility | Yes (M4) | `desktop_gui_tauri_standards.md` section 9 | Yes | Test report |
| Supply chain | Yes | `deps`, `secrets`, `licenses`, `sbom` gates; Scorecard | Yes | CI artifacts |
| Documentation integrity | Yes | `python tools/gate.py docs` | Yes | CI log |
| Matcher benchmark and NFIQ 2 | Ops gate | Validation procedure outside CI | Yes for Ops gate | Validation report (lab QMS) |

## 8. Exceptions and deviations

| Standard/control/rule | Reason | Risk | Compensating control | Owner | Approval | Expiration/follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| Named owners for all roles | Names not yet provided | No accountable approval of risk, releases or validation | No release beyond internal engineering builds; no casework | Product Owner (TBD) | Pending | Before M1 release; release blocker |
| Encrypted case store (`forensic_evidence...` sections 2, 10) | Not implemented | Class E outputs written unencrypted | OS full-disk encryption (BitLocker, FileVault, LUKS) on every machine that handles outputs; outputs only on that volume; examiner deletes outputs per case retention | Security Owner (TBD) | Pending | M1 per `docs/prd.md`; no later than M2 |
| Custody log and signed reports | Not implemented | No tamper-evident record of processing | Examiner records SHA-256 of inputs and outputs (`certutil -hashfile <f> SHA256`, `shasum -a 256`, `sha256sum`) and parameters in the lab case record | Forensic Quality Manager (TBD) | Pending | M1 per `docs/prd.md`; no later than M2 |
| Legacy `fingerprint_extract.py` (413 lines, untyped, no tests, exceeds 300-line soft limit) | Refactor in progress | Regressions; unreviewable size | Characterization tests before refactor; no casework use | Quality/Release Owner (TBD) | Pending | **Closed 2026-10-16 (M0, Handoff_1):** typed `src/ridge` package, largest module 184 lines; bit-identical to v0 on the golden cases (`tests/test_characterization.py`) |
| Legacy decoding (`Image.open` without `formats=`, no size or pixel limits, decoder errors swallowed with OpenCV fallback) | Legacy code | Exotic decoders reachable (for example EPS via Ghostscript), resource exhaustion (CWE-400/409/770), hidden failures | Run only on synthetic or self-made photos; no case material until M0 code replaces it | Security Owner (TBD) | Pending | **Closed 2026-10-16 (M0, Handoff_1):** allow-listed single decoder, size/pixel limits, typed errors, pipeline memory bounds (CWE-789); `tests/test_image_io.py`, `tests/test_hardening.py` |
| Silent overwrite of outputs; same-stem collisions (`a.jpg` and `a.png` both write `a_fingerprint.png`) | Legacy code | Loss or confusion of outputs | Use a fresh output directory per run | Quality/Release Owner (TBD) | Pending | **Overwrite closed 2026-10-16 (M0):** no-clobber atomic publish, `--overwrite` explicit. **Open:** a same-stem collision now fails the second file loudly instead of overwriting; unique naming arrives with the case store (M1) |
| Unpinned dependencies (`>=` in `requirements.txt`) | Legacy setup | Irreproducible results, supply-chain exposure | Use the developer `.venv`; record `pip freeze` with any output | Quality/Release Owner (TBD) | Pending | **Closed 2026-10-16 (M0):** `requirements.txt` removed; universal hash-pinned `requirements.lock` / `requirements-dev.lock`, installs use `--require-hashes` |
| `pillow-heif` wheels bundle libheif/libde265 (LGPL) and the x265 encoder (GPL); package metadata says BSD-3-Clause | HEIC decoding needed for iPhone photos | Licence obligations if Ridge is ever distributed outside the organisation; native decoder attack surface (libheif CVE history) | Internal use only; `licenses` gate prints the note; evaluate `pi-heif` (decoder-only, no x265) | Security Owner + legal (TBD) | Pending | Before M1 release |
| Bit-identical golden results only on the reference platform (Windows, recorded library versions) | OpenCV/NumPy SIMD paths and libm differ across OS/CPU | Cross-platform reproducibility claims overstated | Other platforms must agree on >= 99.9% of pixels (`tests/test_characterization.py`); reproducibility claimed per (release, OS, CPU architecture) only | Forensic Quality Manager (TBD) | Pending | Measure on CI matrix; revisit at M2 |
| GUI rules (`desktop_gui_tauri_standards.md`) | GUI not built | None today | Rules apply from first GUI commit | Product Owner (TBD) | N/A | M4 |
| Method validation (ISO/IEC 17025 7.2.2) | Not yet performed | Unvalidated method in casework | Casework use forbidden | Forensic Quality Manager (TBD) | Pending | Ops gate |
| DPIA (LED Art. 27) | Not yet performed | Unlawful or disproportionate processing | Casework use forbidden; volunteer data collection waits for DPO advice | DPO (TBD) | Pending | Ops gate (volunteer collection: before collection) |
| AFIS exchange format | Pending vendor confirmation (`docs/prd.md` OQ-4) | Wrong export format | Lossless 500 ppi PNG export only (M2); no exchange-format work beyond design | Product Owner (TBD) | Pending | M3 |
| NFIQ 2 on photo-derived images | Outside the nominal scope of ISO/IEC 29794-4 | Over-reliance on scores | Scores labelled indicative; thresholds from validation only | Forensic Quality Manager (TBD) | Pending | Ops gate |
| ASVS chapters V3, V4, V7, V9, V10, V12, V17 | No web front end, network API, sessions, tokens, OAuth, network or WebRTC | None while offline | Reassess when any network component appears; V3 partly applies to the GUI WebView (M4) | Security Owner (TBD) | N/A | Trigger-based |
| Multi-user, tenancy, RLS | Single examiner per workstation | None today | Reassess if a lab server or shared store is added | Security Owner (TBD) | N/A | Trigger-based |

## 9. Release evidence locations

| Evidence | Location |
| --- | --- |
| Standards profile | `Instruction_documentation/Project_Standards_Profile.md` |
| Requirements and traceability | `docs/prd.md` (requirement IDs) linked to tests; traceability table location defined in `docs/prd.md` |
| Threat model | `docs/architecture.md` |
| Architecture/design records | `docs/architecture.md` (section 13 ADRs), `docs/adr/` when created |
| Test and gate reports | GitHub Actions run artifacts for the release commit |
| Security scan reports | GitHub code scanning (CodeQL SARIF), gate artifacts (bandit, pip-audit, gitleaks, licenses, SBOM) |
| Validation report, DPIA, AI Act assessment | Laboratory QMS and DPO records (outside the repository); referenced here by document ID once approved |
| Release checklist | Completed copy of `release_readiness_checklist.md` sections, recorded in the release handoff |
| Handoffs | `Instruction_documentation/Handoff/Handoff_<N>.md` |

## 10. Review cadence

Review this profile when:

- A milestone is completed or `docs/prd.md` changes scope or milestones.
- An owner is named or changes.
- A dependency that affects pixels (numpy, OpenCV, Pillow, pillow-heif, libheif) or a supported platform changes.
- A new input format, export format, ML component, network capability, or data store is added.
- The AFIS vendor confirms the exchange format.
- The DPO/legal assessment of LED, ZVOPOKD, GDPR or the AI Act changes.
- A standard edition listed in section 4 changes, or before any release that cites it.
