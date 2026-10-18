# Ridge Project Standards Profile

Last verified: 2026-10-18
Derived from `Project_Standards_Profile_Template.md`. Review triggers are in section 10. Product requirements: `docs/prd.md`. Design: `docs/architecture.md` (ADR table in section 13; `docs/adr/` when created).

## 1. Project identification

| Field | Value |
| --- | --- |
| Project name | Ridge |
| Repository | GitHub (internal, private). Default branch protected. |
| Product Owner | Interim: the product owner (GitHub ZvonkoNS), 2026-10-18 (OQ-10) |
| Security Owner | Interim: the product owner (GitHub ZvonkoNS), 2026-10-18 (OQ-10) |
| Quality/Release Owner | Interim: the product owner (GitHub ZvonkoNS), 2026-10-18 (OQ-10) |
| Data Protection Officer | Interim: the product owner (GitHub ZvonkoNS), 2026-10-18 (OQ-10); an independent holder should be named before casework use |
| Forensic Quality Manager (ISO/IEC 17025) | Interim: the product owner (GitHub ZvonkoNS), 2026-10-18 (OQ-10); an independent holder should be named before casework use |
| Last reviewed | 2026-10-18 |

Every owner role is named, on an interim basis, by the product owner (2026-10-18). The Data Protection Officer and the Forensic Quality Manager are normally independent of the product owner, so independent holders should be named before Ridge is used for casework (see section 8).

## 2. Product and deployment context

| Field | Value |
| --- | --- |
| Product type | Offline forensic image-enhancement tool: CLI, Python library and desktop GUI (Tauri v2 + React + TypeScript over the Python sidecar, engineering build since 2026-10-18). Distribution: internal, proprietary, own organisation only. |
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
| Case store (implemented, M1) | Per `docs/architecture.md` section 8: files plus JSONL custody log, AES-256-GCM encrypted content-addressed blobs (ADR-008 proposed; SQLite is the documented alternative) | `backend_database_rls_rpc_standards.md`, ISO/IEC 9075 only if SQLite is chosen, ASVS V11/V14 |
| Custody log and reports (implemented, M1) | SHA-256, RFC 8785 canonical JSON, Ed25519 | `forensic_evidence_and_biometric_data_standards.md` |
| Key custody (implemented, M1) | OS keystore (Windows DPAPI, macOS Keychain, Linux Secret Service) plus Argon2id passphrase wrapping | `environment_configuration_and_secrets.md`, RFC 9106 |
| Sidecar (implemented, M4) | JSON-RPC 2.0 over stdio (`ridge-sidecar`, protocol `ridge.sidecar/1`) | `edge_function_standards.md` |
| Desktop GUI (implemented, M4 engineering build) | Tauri 2.12.1 (Rust 1.98.0, pinned in `gui/src-tauri/rust-toolchain.toml`), tauri-plugin-dialog 2.8.1 (Rust-side only), React 19.3, TypeScript 6.0 (strict), Vite 8, Motion 14, Atkinson Hyperlegible fonts (OFL-1.1, bundled). ECMAScript target ES2022 (`chrome120`, `safari16`: WebView2 on Windows 11, WKWebView on macOS 13+, WebKitGTK 2.40+) | `desktop_gui_tauri_standards.md`, ECMA-262, WCAG 2.2 AA; ADR-010, ADR-011 |
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
| TypeScript (M4) | ECMA-262 (ES2022 target), TypeScript 6.0 strict with `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride` | `desktop_gui_tauri_standards.md` | ESLint (typescript-eslint strict type-checked, React hooks), tsc, Prettier, Vitest with axe-core | `python tools/gate.py gui` (runs `npm ci`, `npm run lint`, `npm run typecheck`, Prettier, `npm test`, `npm run build`, `npm audit`) |
| Rust (M4) | Rust 1.98.0 (pinned), edition 2021 | Clippy with `unwrap_used`, `expect_used` and `panic` denied, `unsafe_code` forbidden (crate lints) | cargo fmt, cargo clippy, cargo test, cargo audit, cargo deny | `python tools/gate.py gui` (runs `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`, `cargo audit`, `cargo deny check`) |
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
- SBOM required: yes (`python tools/gate.py sbom`, CycloneDX) for every release; the GUI's npm and Cargo SBOMs come from `python tools/gate.py gui` (`build/sbom-npm.cdx.json`, `build/sbom-cargo.cdx.json`).
- Penetration test or independent security review: yes, before the Ops gate.
- Independent review: yes, method validation reviewed by the Forensic Quality Manager; security review by someone other than the author of the change.

## 7. Testing and verification evidence

| Test or verification type | Required? | Tool/command | Release blocker? | Evidence location |
| --- | --- | --- | --- | --- |
| Lint/format | Yes | `python tools/gate.py lint`, `python tools/gate.py format` | Yes | CI log |
| Typecheck | Yes | `python tools/gate.py typecheck` | Yes | CI log |
| Unit tests and coverage | Yes | `python tools/gate.py test` | Yes | CI log, coverage report |
| Golden characterization | Yes (M0) | part of `test`: live v0 run (bit-identical on each platform tested) and per-architecture goldens `tests/golden/v0-<arch>.*`; every platform in the full CI matrix per release, Apple silicon on pixel-affecting pull requests (`arm64.yml`) | Yes | CI log |
| Determinism | Yes (M0) | part of `test` | Yes | CI log |
| Hostile input (malformed, oversized, bombs, wrong format) | Yes (M0) | part of `test` | Yes | CI log |
| Fuzzing of decoders | Yes (M1) | hypothesis in `test`; atheris campaigns scheduled | Findings block | CI artifacts |
| Custody/report integrity | Yes (M1) | part of `test` | Yes | CI log |
| IPC/JSON-RPC security | Yes (M4) | part of `test` (sidecar schemas, fuzz) and `gui` (Rust request types, validation, capability and CSP tests, live sidecar test) | Yes | Gate log |
| E2E/smoke | Yes | CLI smoke on synthetic data; GUI: component flows with mocked IPC (Vitest) plus a live Rust-to-sidecar test; Tauri WebDriver E2E not implemented (exception, section 8) | Yes | Gate log |
| Accessibility | Yes (M4) | axe-core in Vitest (`python tools/gate.py gui`); manual NVDA/VoiceOver pass before each GUI release (`desktop_gui_tauri_standards.md` section 9), run by the product owner from `docs/screen_reader_test.md` (decided 2026-10-18) | Yes | Gate log, release handoff |
| Supply chain | Yes | `deps`, `secrets`, `licenses`, `sbom` gates; Scorecard | Yes | CI artifacts |
| Documentation integrity | Yes | `python tools/gate.py docs` | Yes | CI log |
| Matcher benchmark and NFIQ 2 | Ops gate | Validation procedure outside CI; metrics with `ridge-validate` (tested in CI on synthetic scores) | Yes for Ops gate | Validation report (lab QMS) |

## 8. Exceptions and deviations

| Standard/control/rule | Reason | Risk | Compensating control | Owner | Approval | Expiration/follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| CI test matrix on every pull request (3 OS x Python 3.12-3.14) | Owner decision 2026-10-17: keep GitHub Actions usage to a minimum (account spending limit reached twice that day) | A platform- or version-specific defect is found later, at the next full-matrix run instead of on the pull request | Local `python tools/gate.py all` (Windows, 3.13) before every push; Linux 3.12 CI on every code pull request; Apple silicon pixel tests whenever pixel-affecting code changes; full matrix on demand and required for every release (`release_readiness_checklist.md`) | Quality/Release Owner (TBD) | Product owner, 2026-10-17 | Review when the account's Actions budget changes |
| Named owners for all roles | Names not yet provided | No accountable approval of risk, releases or validation | No release beyond internal engineering builds; no casework | Product Owner (TBD) | Pending | Before M1 release; release blocker |
| Encrypted case store (`forensic_evidence...` sections 2, 10) | Not implemented | Class E outputs written unencrypted | OS full-disk encryption (BitLocker, FileVault, LUKS) on every machine that handles outputs; outputs only on that volume; examiner deletes outputs per case retention | Security Owner (TBD) | Pending | **Closed for casework 2026-10-17 (M1, Handoff_3):** `ridge-case` stores evidence, outputs, reports and custody encrypted. The plain `ridge` command stays unencrypted R&D mode and says so (FR-27). |
| Custody log and signed reports | Not implemented | No tamper-evident record of processing | Examiner records SHA-256 of inputs and outputs (`certutil -hashfile <f> SHA256`, `shasum -a 256`, `sha256sum`) and parameters in the lab case record | Forensic Quality Manager (TBD) | Pending | **Closed 2026-10-17 (M1, Handoff_3):** hash-chained encrypted custody log, Ed25519-signed RFC 8785 reports, `ridge-case verify`. Open: out-of-band countersigning (OQ-8). |
| Legacy `fingerprint_extract.py` (413 lines, untyped, no tests, exceeds 300-line soft limit) | Refactor in progress | Regressions; unreviewable size | Characterization tests before refactor; no casework use | Quality/Release Owner (TBD) | Pending | **Closed 2026-10-16 (M0, Handoff_1):** typed `src/ridge` package, largest module 184 lines; bit-identical to v0 on the golden cases (`tests/test_characterization.py`) |
| Legacy decoding (`Image.open` without `formats=`, no size or pixel limits, decoder errors swallowed with OpenCV fallback) | Legacy code | Exotic decoders reachable (for example EPS via Ghostscript), resource exhaustion (CWE-400/409/770), hidden failures | Run only on synthetic or self-made photos; no case material until M0 code replaces it | Security Owner (TBD) | Pending | **Closed 2026-10-16 (M0, Handoff_1):** allow-listed single decoder, size/pixel limits, typed errors, pipeline memory bounds (CWE-789); `tests/test_image_io.py`, `tests/test_hardening.py` |
| Silent overwrite of outputs; same-stem collisions (`a.jpg` and `a.png` both write `a_fingerprint.png`) | Legacy code | Loss or confusion of outputs | Use a fresh output directory per run | Quality/Release Owner (TBD) | Pending | **Overwrite closed 2026-10-16 (M0):** no-clobber atomic publish, `--overwrite` explicit. **Open:** a same-stem collision now fails the second file loudly instead of overwriting; unique naming arrives with the case store (M1) |
| Unpinned dependencies (`>=` in `requirements.txt`) | Legacy setup | Irreproducible results, supply-chain exposure | Use the developer `.venv`; record `pip freeze` with any output | Quality/Release Owner (TBD) | Pending | **Closed 2026-10-16 (M0):** `requirements.txt` removed; universal hash-pinned `requirements.lock` / `requirements-dev.lock`, installs use `--require-hashes` |
| `pillow-heif` wheels bundle libheif/libde265 (LGPL) and the x265 encoder (GPL); package metadata says BSD-3-Clause | HEIC decoding needed for iPhone photos | Licence obligations if Ridge is ever distributed outside the organisation; native decoder attack surface (libheif CVE history) | Internal use only; `licenses` gate prints the note; evaluate `pi-heif` (decoder-only, no x265) | Security Owner + legal (TBD) | Pending | Before M1 release |
| Results differ between CPU architectures (x86-64 vs arm64; observed 2026-10-17, Handoff_2) | OpenCV/NumPy SIMD floating point | Prints from different architectures not interchangeable | Reproducibility and validation per architecture (PRD NFR-3, ADR-009); live v0 bit-identical check on every platform; per-architecture goldens; casework only on validated architectures (OQ-15); cross-architecture envelope test (`tests/test_cross_architecture.py`) | Forensic Quality Manager (TBD) | NFR-3 change directed by the product owner on 2026-10-17 (PR #1); Forensic Quality Manager confirmation pending | Decide casework architectures before M5 |
| GUI rules (`desktop_gui_tauri_standards.md`) | GUI not built | None today | Rules apply from first GUI commit | Product Owner (TBD) | N/A | **Closed 2026-10-18 (M4, Handoff_15):** GUI built under these rules; the deviations are the rows below |
| Passphrase entered in a WebView window, not an OS-native dialog (architecture §7.3 "native prompt") | Tauri has no password dialog; OS-native prompts need `unsafe` FFI (Windows, macOS) or a shell helper (Linux), two of three untestable here | A compromised bundle could read the passphrase in the prompt window | Separate Rust-owned window with its own page and a capability limited to three commands; label check in each handler; same CSP (no workers), navigation lock and new-window denial; the main WebView never sees the passphrase; zeroised Rust buffers; five attempts; ADR-010 | Security Owner (TBD) | Pending (decided in the autonomous window of 2026-10-18) | Before the first GUI release |
| GUI E2E with Tauri WebDriver (`desktop_gui_tauri_standards.md` §12, `npm run test:e2e`) | Needs msedgedriver/WebKitWebDriver per platform; not set up yet | A defect in the wiring between the WebView, Rust and the sidecar is found late | Vitest component flows with mocked IPC; Rust unit tests of every command's validation; live Rust-to-sidecar test over real stdio; manual smoke run of the built app | Quality/Release Owner (TBD) | Pending | Before the first GUI release |
| GUI gate in CI on every pull request | Owner decision 2026-10-17 to keep GitHub Actions minimal; a Rust build costs many runner minutes | A GUI defect reaches `main` when the local gate was skipped | `python tools/gate.py all` includes `gui` and runs locally before every push; `.github/workflows/gui.yml` runs on demand and for release tags; the full matrix is required for releases | Quality/Release Owner (TBD) | Product owner, 2026-10-17 (Actions policy) | Review with the Actions exception |
| Release packaging of the sidecar (signed PyInstaller one-folder build in the Tauri bundle, architecture §10) | Frozen sidecar built and checked (`tools/build_sidecar.py`, 2026-10-18). Windows installers (MSI and per-user NSIS) built and smoke-tested on 2026-10-18 (architecture §10). Code signing needs the laboratory's certificate and is not done | Unsigned installers trigger Windows SmartScreen warnings and cannot be verified by publisher | Engineering builds run the sidecar from the developer virtualenv (debug builds only); release builds look for it only in the bundle's resources; the frozen build is checked for the keystore backend and smoke-tested over stdio | Quality/Release Owner (interim: product owner) | Pending: certificate | Before the first GUI release |
| PyInstaller bootloader in the frozen sidecar (GPL-2.0-or-later with the bootloader exception) | Needed to ship the Python sidecar without a Python installation | Licence obligations if the exception did not apply | The bootloader exception permits distributing frozen applications under any licence; PyInstaller itself is a build tool pinned in `requirements-build.lock` and is not shipped; internal distribution only | Legal (TBD) | Pending | Before any external distribution |
| Rust advisories RUSTSEC-2024-0370 (`proc-macro-error` unmaintained) and RUSTSEC-2024-0429 (`glib` `VariantStrIter` unsound) | Transitive dependencies of Tauri's Linux WebKitGTK stack (gtk 0.18); no fixed version is reachable without upstream changes | A memory-safety defect in GVariant string iteration on Linux; an unmaintained compile-time macro helper | Ridge never iterates GVariant string arrays; `proc-macro-error` runs only at compile time; ignores are listed with reasons in `gui/src-tauri/.cargo/audit.toml` and `deny.toml`; re-checked by every `cargo audit` / `cargo deny` run | Security Owner (TBD) | Pending | Remove when Tauri's Linux stack moves to gtk-rs >= 0.20 |
| Mozilla Public License 2.0 crates in the GUI's Rust dependency tree (through Tauri) | Upstream dependencies of Tauri | File-level copyleft obligations if Ridge were distributed outside the organisation | Internal distribution only; listed by `cargo deny check licenses`; the source of MPL files is unmodified upstream | Legal + Security Owner (TBD) | Pending | Before any external distribution |
| Method validation (ISO/IEC 17025 7.2.2) | Not yet performed | Unvalidated method in casework | Casework use forbidden | Forensic Quality Manager (TBD) | Pending | Ops gate |
| DPIA (LED Art. 27) | Not yet performed | Unlawful or disproportionate processing | Casework use forbidden; volunteer data collection waits for DPO advice | DPO (TBD) | Pending | Ops gate (volunteer collection: before collection) |
| AFIS exchange format | Pending vendor confirmation (`docs/prd.md` OQ-4) | Wrong export format | Lossless 500 ppi PNG export only (M2); no exchange-format work beyond design | Product Owner (TBD) | Pending | M3 |
| NFIQ 2 on photo-derived images | Outside the nominal scope of ISO/IEC 29794-4 | Over-reliance on scores | Scores labelled indicative; thresholds from validation only | Forensic Quality Manager (TBD) | Pending | Ops gate |
| Automatic minutiae (M3) not validated; Ridge-specific JSON instead of ISO/IEC 39794-2 / ANSI/NIST-ITL Type-9 | Exchange format open (OQ-4); no reference extractor benchmark yet | False or missed minutiae mislead an examiner | Off by default (`--minutiae`), labelled "unvalidated" in every report, never used for matching; benchmark against a reference extractor in the validation study | Forensic Quality Manager (TBD) | Pending | M5 validation / OQ-4 |
| Ridge-period scale for 500 ppi exports (assumed 0.47 mm ridge distance, ±15 %) | No ruler in many case photos | Export scale wrong by tens of percent; matcher comparisons affected | Method and uncertainty recorded in every report; ruler calibration (`--ruler`) preferred; values replaced by validation results (PRD §12) | Forensic Quality Manager (TBD) | Pending | M5 validation |
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
